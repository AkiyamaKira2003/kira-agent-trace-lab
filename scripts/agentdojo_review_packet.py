"""Metadata-only AgentDojo review packet and *provisional* blind-review checks.

Never execute pinned task code or recorded tool calls. The packet contains only
immutable source pointers, hashes, action ordinals and tool names: reviewers
must inspect source and sensitive arguments privately. Free-form identity
claims cannot authenticate human reviewers, so agreement is NEVER certified.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib import request

from agent_trace_lab.schema import SuiteError
from scripts.audit_agentdojo_sampling import _parse_json
from scripts.audit_agentdojo_strata import (
    MAX_MANIFEST, MAX_METADATA, MANIFEST_PATH, SOURCE_REV, SPEC_PATH,
    _read_json_bounded, validate_manifest, validate_spec,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "docs" / "agentdojo_task_sources.json"
SOURCE_CAP = 131072
MAX_REVIEW_INPUT = 131072
SOURCE_EXPECTED = (
    ("banking", 19450, "37af838194f001af80cc040315bcb2d69d0112324d424f9a323473b41b317f82"),
    ("slack", 26012, "25e43a0c58109765da090aa2f01bfb0892aaee70ca1622028074d7b49443a57b"),
    ("travel", 76962, "757f0e28208f92c2082e016469654524cb1120ec10928ce229da15fe32f6d3ee"),
    ("workspace", 55415, "d2a550b812b7f40ee2dea17ac19d44f2dd063d103524118216b563eca6e44171"),
)
LABELS = {"within_scope", "out_of_scope", "abstain"}
IDENTITY_RE = re.compile(r"[a-zA-Z0-9_-]{3,64}\Z")
SPAN_RE = re.compile(r"L[1-9][0-9]{0,5}(?:-L[1-9][0-9]{0,5})?\Z")


def validate_sources(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "upstream_repository", "source_revision", "license",
        "sources", "human_authorization", "task_intent_and_action_arguments",
    }:
        raise SuiteError("invalid task-source manifest")
    if (value["schema_version"] != "agentdojo-pinned-task-sources-1"
            or value["upstream_repository"] != "https://github.com/ethz-spylab/agentdojo"
            or value["source_revision"] != SOURCE_REV or value["license"] != "MIT"
            or value["human_authorization"] != "unverified"
            or value["task_intent_and_action_arguments"] != "manual_independent_review_required"):
        raise SuiteError("task-source provenance or review boundary differs")
    expected = [
        {
            "suite": suite, "path": f"src/agentdojo/default_suites/v1/{suite}/user_tasks.py",
            "sha256": digest, "size_bytes": size,
            "task_classes_verified": ["UserTask0", "UserTask1"],
        }
        for suite, size, digest in SOURCE_EXPECTED
    ]
    if value["sources"] != expected:
        raise SuiteError("source hash, task class or source selection changed")
    return value


def verify_pinned_task_sources(sources: dict[str, Any]) -> int:
    """Explicit opt-in, bounded read of four immutable code files, never import."""
    for entry in sources["sources"]:
        url = (f"https://raw.githubusercontent.com/ethz-spylab/agentdojo/"
               f"{SOURCE_REV}/{entry['path']}")
        req = request.Request(url, headers={"User-Agent": "KiraTrace-TaskSourceAudit/1"})
        with request.urlopen(req, timeout=15) as resp:
            raw = resp.read(SOURCE_CAP + 1)
        if (len(raw) != entry["size_bytes"]
                or len(raw) > SOURCE_CAP
                or hashlib.sha256(raw).hexdigest() != entry["sha256"]):
            raise SuiteError("pinned task source size or SHA-256 mismatch")
        for index in (0, 1):
            if re.search(rb"(?m)^class UserTask" + str(index).encode() + rb"\(", raw) is None:
                raise SuiteError("pinned task definition missing")
    return len(sources["sources"])


def make_packet(manifest: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    by_suite = {row["suite"]: row for row in sources["sources"]}
    records: list[dict[str, Any]] = []
    for index, row in enumerate(manifest["records"]):
        task = by_suite[row["suite"]]
        records.append({
            "slot_id": f"slot_{index:02d}",
            "suite": row["suite"], "task_id": f"user_task_{row['task_index']}",
            "condition": row["condition"], "availability": row["status"],
            "run_source_path": row["source_path"], "run_sha256": row["sha256"],
            "task_source_path": task["path"], "task_source_sha256": task["sha256"],
            "task_source_url": (f"https://github.com/ethz-spylab/agentdojo/blob/"
                                f"{SOURCE_REV}/{task['path']}"),
            "actions": [
                {"action_id": f"slot_{index:02d}:action_{n:03d}", "tool": tool, "ordinal": n}
                for n, tool in enumerate(row["observed_tools"])
            ],
            "review_status": "pending_private_source_review" if row["status"] == "present"
                             else "unavailable_no_review",
            "human_authorization": "abstain",
        })
    return {
        "schema_version": "agentdojo-blinded-review-packet-1",
        "preregistration_commit": manifest["preregistration_commit"],
        "source_revision": SOURCE_REV,
        "data_policy": "metadata_only_no_arguments_prompts_recipients_or_publisher_outcomes",
        "independent_reviewer_identity_verified": False,
        "records": records,
    }


def audit_provisional_reviews(packet: dict[str, Any], review_input: Any) -> dict[str, Any]:
    """Validate review shape and count provisional pairs; never certify identities.

    Reviewer names/evidence references are untrusted assertions. Verification of
    actual distinct humans, blinded process and cited source spans is external.
    """
    if not isinstance(review_input, dict) or set(review_input) != {
        "schema_version", "reviewers", "reviews",
    } or review_input["schema_version"] != "agentdojo-blinded-review-submission-1":
        raise SuiteError("review submission schema invalid")
    reviewers = review_input["reviewers"]
    if not isinstance(reviewers, list) or len(reviewers) != 2:
        raise SuiteError("two distinct independent reviewers are required")
    ids = []
    for reviewer in reviewers:
        if (not isinstance(reviewer, dict) or set(reviewer) != {"reviewer_id", "identity_evidence_ref"}
                or not isinstance(reviewer["reviewer_id"], str)
                or IDENTITY_RE.fullmatch(reviewer["reviewer_id"]) is None
                or not isinstance(reviewer["identity_evidence_ref"], str)
                or not 8 <= len(reviewer["identity_evidence_ref"]) <= 256):
            raise SuiteError("reviewer identity provenance insufficient")
        ids.append(reviewer["reviewer_id"])
    if ids[0] == ids[1]:
        raise SuiteError("duplicate reviewer identity")
    actions = {
        action["action_id"]: (row, action)
        for row in packet["records"] if row["availability"] == "present"
        for action in row["actions"]
    }
    submissions = review_input["reviews"]
    if not isinstance(submissions, list) or len(submissions) > 2 * len(actions):
        raise SuiteError("review count invalid")
    paired: dict[str, dict[str, str]] = {}
    for item in submissions:
        if not isinstance(item, dict) or set(item) != {
            "reviewer_id", "action_id", "label", "task_source_sha256",
            "task_source_span", "rationale",
        }:
            raise SuiteError("review row schema invalid")
        reviewer_id, action_id = item["reviewer_id"], item["action_id"]
        if (not isinstance(reviewer_id, str) or reviewer_id not in ids
                or not isinstance(action_id, str) or action_id not in actions
                or not isinstance(item["label"], str) or item["label"] not in LABELS):
            raise SuiteError("unknown reviewer/action or invalid label")
        row, _ = actions[action_id]
        if (item["task_source_sha256"] != row["task_source_sha256"]
                or not isinstance(item["task_source_span"], str)
                or SPAN_RE.fullmatch(item["task_source_span"]) is None
                or not isinstance(item["rationale"], str)
                or not 12 <= len(item["rationale"]) <= 1200):
            raise SuiteError("source-bound rationale is incomplete")
        pair = paired.setdefault(action_id, {})
        if reviewer_id in pair:
            raise SuiteError("duplicate reviewer action label")
        pair[reviewer_id] = item["label"]
    joint = [labels for labels in paired.values() if len(labels) == 2]
    agreements = sum(labels[ids[0]] == labels[ids[1]] and labels[ids[0]] != "abstain"
                     for labels in joint)
    contested = sum(labels[ids[0]] != labels[ids[1]] for labels in joint)
    abstentions = sum("abstain" in labels.values() for labels in joint)
    return {
        "status": "PROVISIONAL_ONLY_IDENTITY_AND_SOURCE_CITATIONS_NOT_INDEPENDENTLY_VERIFIED",
        "planned_exposure_slots": len(packet["records"]),
        "unavailable_exposure_slots": sum(row["availability"] != "present" for row in packet["records"]),
        "reviewable_action_count": len(actions),
        "paired_action_reviews": len(joint),
        "single_or_unreviewed_actions": len(actions) - len(joint),
        "provisional_nonabstain_agreement": agreements,
        "provisional_disagreement_needs_adjudication": contested,
        "pairs_with_abstentions": abstentions,
        "accepted_independent_agreements": 0,
        "independent_reviewer_identity_verified": False,
        "source_span_meaning_verified": False,
        "human_authorization_labels": "abstain",
        "population_safety_accuracy": None,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-upstream", action="store_true",
                        help="check four immutable task sources by SHA-256, no code execution")
    parser.add_argument("--write-packet", type=Path,
                        help="create metadata-only packet without overwriting existing files")
    parser.add_argument("--reviews", type=Path,
                        help="evaluate a local review submission as PROVISIONAL only")
    args = parser.parse_args()
    try:
        spec = validate_spec(_read_json_bounded(SPEC_PATH, MAX_METADATA))
        manifest = validate_manifest(spec, _read_json_bounded(MANIFEST_PATH, MAX_MANIFEST))
        sources = validate_sources(_read_json_bounded(SOURCES_PATH, 16384))
        upstream_count = verify_pinned_task_sources(sources) if args.check_upstream else 0
        packet = make_packet(manifest, sources)
        if args.write_packet is not None:
            with args.write_packet.open("xb") as fd:
                fd.write((json.dumps(packet, indent=2, ensure_ascii=True) + "\n").encode("utf-8"))
        if args.reviews is not None:
            report = audit_provisional_reviews(packet, _read_json_bounded(args.reviews, MAX_REVIEW_INPUT))
        else:
            report = {
                "status": "REVIEW_PACKET_READY_NO_INDEPENDENT_REVIEWS",
                "planned_slots": len(packet["records"]),
                "available_slots": sum(r["availability"] == "present" for r in packet["records"]),
                "missing_slots": sum(r["availability"] == "missing" for r in packet["records"]),
                "action_metadata_count": sum(len(r["actions"]) for r in packet["records"]),
                "accepted_independent_agreements": 0,
                "human_authorization_labels": "abstain",
                "publisher_flags_excluded": True,
                "tool_arguments_and_task_prompts_excluded": True,
            }
        report["pinned_task_sources_rechecked_online"] = upstream_count
        print(json.dumps(report, sort_keys=True))
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
