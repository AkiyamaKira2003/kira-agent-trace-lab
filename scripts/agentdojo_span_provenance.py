"""Opt-in SHA proof for AgentDojo task-code line citations, never code execution.

This verifies that a claimed line selection is byte-identical to a pinned MIT
source file. It does NOT verify semantic relevance, real human reviewer identity,
review independence, authorization or consent. Outputs contain hashes/counts
only, never source text, review rationale or model/tool arguments.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib import request

from agent_trace_lab.schema import SuiteError
from scripts.agentdojo_review_packet import (
    MAX_REVIEW_INPUT, ROOT, SOURCE_CAP, SOURCES_PATH,
    audit_provisional_reviews, make_packet, validate_sources,
)
from scripts.audit_agentdojo_strata import (
    MAX_MANIFEST, MAX_METADATA, MANIFEST_PATH, SOURCE_REV, SPEC_PATH,
    _read_json_bounded, validate_manifest, validate_spec,
)

MAX_RANGES = 4
MAX_LINES_PER_RANGE = 12
MAX_TOTAL_LINES = 24
RANGE_RE = re.compile(r"L([1-9][0-9]{0,5})(?:-L([1-9][0-9]{0,5}))?\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


def parse_line_ranges(citation: str) -> list[tuple[int, int]]:
    if not isinstance(citation, str) or not 1 <= len(citation) <= 100:
        raise SuiteError("invalid source-span citation")
    pieces = citation.split(",")
    if not 1 <= len(pieces) <= MAX_RANGES:
        raise SuiteError("source-span count out of bounds")
    ranges = []
    total = 0
    previous_end = 0
    for piece in pieces:
        match = RANGE_RE.fullmatch(piece)
        if match is None:
            raise SuiteError("source-span syntax invalid")
        first = int(match.group(1))
        last = int(match.group(2)) if match.group(2) else first
        if first <= previous_end or last < first:
            raise SuiteError("source-span reversed, unordered or overlapping")
        if last - first + 1 > MAX_LINES_PER_RANGE:
            raise SuiteError("source-span range too wide")
        total += last - first + 1
        if total > MAX_TOTAL_LINES:
            raise SuiteError("source-span total line cap exceeded")
        previous_end = last
        ranges.append((first, last))
    return ranges


def cite_span_digest(source_bytes: bytes, citation: str) -> str:
    """Digest exact raw lines with range delimiters; no decoded/reformatted text."""
    if not isinstance(source_bytes, bytes) or not source_bytes or len(source_bytes) > SOURCE_CAP:
        raise SuiteError("task-source bytes missing or oversized")
    lines = source_bytes.splitlines(keepends=True)
    ranges = parse_line_ranges(citation)
    if ranges[-1][1] > len(lines):
        raise SuiteError("source-span line outside pinned task definition")
    digest = hashlib.sha256(b"agentdojo-cited-task-lines-v1\x00")
    for first, last in ranges:
        block = b"".join(lines[first - 1:last])
        digest.update(first.to_bytes(4, "big"))
        digest.update(last.to_bytes(4, "big"))
        digest.update(len(block).to_bytes(4, "big"))
        digest.update(block)
    return digest.hexdigest()


def fetch_pinned_source(entry: dict[str, Any]) -> bytes:
    """Bounded, pinned upstream source only; never imports/executes .py."""
    url = (f"https://raw.githubusercontent.com/ethz-spylab/agentdojo/"
           f"{SOURCE_REV}/{entry['path']}")
    with request.urlopen(
        request.Request(url, headers={"User-Agent": "KiraTrace-CitationProof/1"}),
        timeout=15,
    ) as resp:
        raw = resp.read(SOURCE_CAP + 1)
    if (len(raw) > SOURCE_CAP or len(raw) != entry["size_bytes"]
            or hashlib.sha256(raw).hexdigest() != entry["sha256"]):
        raise SuiteError("source pin mismatch for citation proof")
    return raw


def prevalidate_citation_submission(packet: dict[str, Any], submission: Any) -> dict[str, Any]:
    """Reject v2 schema/record spoofing BEFORE any optional network requests."""
    if not isinstance(submission, dict) or set(submission) != {
        "schema_version", "reviewers", "reviews",
    } or submission["schema_version"] != "agentdojo-citation-review-submission-2":
        raise SuiteError("citation submission version mismatch")
    reviews = submission["reviews"]
    if not isinstance(reviews, list):
        raise SuiteError("invalid review array")
    stripped = {"schema_version": "agentdojo-blinded-review-submission-1",
                "reviewers": submission["reviewers"], "reviews": []}
    for record in reviews:
        if not isinstance(record, dict) or set(record) != {
            "reviewer_id", "action_id", "label", "task_source_sha256",
            "task_source_span", "task_source_span_digest", "rationale",
        }:
            raise SuiteError("citation review fields invalid")
        if (not isinstance(record["task_source_span_digest"], str)
                or SHA_RE.fullmatch(record["task_source_span_digest"]) is None):
            raise SuiteError("citation proof SHA malformed")
        parse_line_ranges(record["task_source_span"])
        stripped["reviews"].append({
            key: value for key, value in record.items() if key != "task_source_span_digest"
        })
    audit_provisional_reviews(packet, stripped)
    return stripped


def validate_citation_proofs(packet: dict[str, Any], submission: Any,
                             sources: dict[str, bytes]) -> dict[str, Any]:
    stripped = prevalidate_citation_submission(packet, submission)
    result = audit_provisional_reviews(packet, stripped)
    reviews = submission["reviews"]
    rows = {
        action["action_id"]: row for row in packet["records"] if row["availability"] == "present"
        for action in row["actions"]
    }
    for record in reviews:
        row = rows[record["action_id"]]
        raw = sources.get(row["suite"])
        if (raw is None or hashlib.sha256(raw).hexdigest() != row["task_source_sha256"]
                or cite_span_digest(raw, record["task_source_span"])
                != record["task_source_span_digest"]):
            raise SuiteError("pinned citation bytes or digest disagree")
    result.update({
        "status": ("CITED_SOURCE_BYTES_VERIFIED_BUT_REVIEWERS_UNVERIFIED" if reviews
                   else "NO_CITED_SOURCE_BYTES_TO_VERIFY"),
        "cited_source_byte_proofs_verified": len(reviews),
        "source_span_meaning_verified": False,
        "accepted_independent_agreements": 0,
        "independent_reviewer_identity_verified": False,
        "human_authorization_labels": "abstain",
    })
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    exclusive = parser.add_mutually_exclusive_group(required=True)
    exclusive.add_argument("--reviews", type=Path, help="local, private v2 review input")
    exclusive.add_argument("--digest-span", nargs=2, metavar=("SUITE", "Lx-Ly"),
                           help="hash exact pinned task lines, without printing source")
    args = parser.parse_args()
    try:
        sources = validate_sources(_read_json_bounded(SOURCES_PATH, 16384))
        entry_by_suite = {entry["suite"]: entry for entry in sources["sources"]}
        if args.digest_span:
            suite, cited = args.digest_span
            if suite not in entry_by_suite:
                raise SuiteError("unknown pinned task source suite")
            value = cite_span_digest(fetch_pinned_source(entry_by_suite[suite]), cited)
            print(json.dumps({"suite": suite, "citation": cited, "span_sha256": value,
                              "source_revision": SOURCE_REV, "source_text_disclosed": False},
                             sort_keys=True))
            return 0
        spec = validate_spec(_read_json_bounded(SPEC_PATH, MAX_METADATA))
        manifest = validate_manifest(spec, _read_json_bounded(MANIFEST_PATH, MAX_MANIFEST))
        packet = make_packet(manifest, sources)
        submission = _read_json_bounded(args.reviews, MAX_REVIEW_INPUT)
        # Full v2 shape + action + reviewer structural gate before any network access.
        prevalidate_citation_submission(packet, submission)
        referenced = {
            row["suite"] for row in packet["records"]
            if any(action["action_id"] == review.get("action_id")
                   for action in row["actions"]
                   for review in submission["reviews"])
        }
        raw = {suite: fetch_pinned_source(entry_by_suite[suite]) for suite in sorted(referenced)}
        print(json.dumps(validate_citation_proofs(packet, submission, raw), sort_keys=True))
    except (OSError, ValueError, UnicodeError, RecursionError, TypeError) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
