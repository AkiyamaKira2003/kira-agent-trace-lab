"""Source-only local OTLP batch-set integrity preflight, NOT a trusted collector.

Verifies only a caller-declared manifest of locally saved HTTP JSON documents.
It cannot authenticate the origin, capture session, or end of a trace.
No runtime dependency, network access, or tool execution is involved.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any

from agent_trace_lab.otlp import import_otlp
from agent_trace_lab.schema import (
    SuiteError,
    _object_no_duplicates,
    _parse_bounded_json_integer,
    _parse_finite_json_float,
    _reject_non_json_number,
    load_json_document,
    load_suite,
)

MAX_POSTS = 8
MAX_POST_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
TRACE_ID = re.compile(r"[0-9a-fA-F]{32}\Z")
SPAN_ID = re.compile(r"[0-9a-fA-F]{16}\Z")


def _deny(message: str) -> None:
    # No user-controlled keys, file names or raw argument strings in errors.
    raise SuiteError(message)


def assemble_declared_capture(directory: Path, manifest: Any) -> dict[str, Any]:
    """Assemble validated stored bytes only when the *declared* set is intact.

    Proof-of-concept only: symlink checks are not a Windows filesystem
    concurrency/security boundary; use a controlled, non-shared local folder.
    """
    if not isinstance(manifest, dict) or set(manifest) != {
        "expected_batch_count", "batches",
    }:
        _deny("manifest declaration must contain exactly the supported fields")
    count = manifest["expected_batch_count"]
    entries = manifest["batches"]
    if type(count) is not int or not 2 <= count <= MAX_POSTS:
        _deny("manifest declared count outside supported local proof limits")
    if not isinstance(entries, list) or len(entries) != count:
        _deny("manifest batch list does not match declared count")
    digests: set[str] = set()
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or set(entry) != {"index", "sha256"}:
            _deny("manifest batch declaration is malformed")
        if type(entry["index"]) is not int or entry["index"] != index:
            _deny("manifest batch indexes are missing, duplicated or unordered")
        digest = entry["sha256"]
        if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
            _deny("manifest batch digest is not a valid lowercase SHA256")
        if digest in digests:
            _deny("manifest contains a repeated batch digest")
        digests.add(digest)

    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        _deny("local capture directory is missing or unsafe")
    names = {f"http-post-{i}.json" for i in range(1, count + 1)}
    # Ignore unrelated metadata receipts but reject any additional
    # HTTP-post-named files, including unexpected suffixes and symlinks.
    detected = {
        path.name for path in directory.iterdir()
        if path.name.startswith("http-post-")
    }
    if detected != names:
        _deny("declared batch files do not match local capture inventory")

    resources: list[Any] = []
    recorded_trace_id: str | None = None
    recorded_span_ids: set[str] = set()
    total_bytes = 0
    total_spans = 0
    for index, entry in enumerate(entries, 1):
        file = directory / f"http-post-{index}.json"
        if file.is_symlink() or not file.is_file():
            _deny("declared local capture file is not a regular file")
        with file.open("rb") as stream:
            raw = stream.read(MAX_POST_BYTES + 1)
        if not raw or len(raw) > MAX_POST_BYTES:
            _deny("capture batch outside per-request byte limit")
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            _deny("capture batch set exceeds total byte limit")
        digest = hashlib.sha256(raw).hexdigest()
        if not hmac.compare_digest(digest, entry["sha256"]):
            _deny("capture batch digest mismatch")
        try:
            doc = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_object_no_duplicates,
                parse_constant=_reject_non_json_number,
                parse_int=_parse_bounded_json_integer,
                parse_float=_parse_finite_json_float,
            )
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise SuiteError("capture batch is not strict UTF-8 OTLP JSON") from exc
        if not isinstance(doc, dict):
            _deny("OTLP capture batch must contain one JSON object")
        groups = doc.get("resourceSpans")
        if not isinstance(groups, list) or not 0 < len(groups) <= 100:
            _deny("capture batch has unsupported OTLP resource groups")
        for resource in groups:
            if not isinstance(resource, dict):
                _deny("capture has malformed resource group")
            scopes = resource.get("scopeSpans", [])
            if not isinstance(scopes, list) or len(scopes) > 100:
                _deny("capture has malformed scope group")
            for scope in scopes:
                if not isinstance(scope, dict):
                    _deny("capture has malformed scope group")
                spans = scope.get("spans", [])
                if not isinstance(spans, list) or len(spans) > 10000:
                    _deny("capture has malformed span group")
                for span in spans:
                    total_spans += 1
                    if total_spans > 10000 or not isinstance(span, dict):
                        _deny("capture exceeds bounded span count or has malformed span")
                    trace_id, span_id = span.get("traceId"), span.get("spanId")
                    # Upstream's ignored/non-tool spans may omit both IDs.
                    # When either is present, validate the pair and prevent
                    # foreign-trace or replay IDs before assembly.
                    if trace_id is None and span_id is None:
                        continue
                    if (not isinstance(trace_id, str)
                            or not TRACE_ID.fullmatch(trace_id)
                            or trace_id.lower() == "0" * 32
                            or not isinstance(span_id, str)
                            or not SPAN_ID.fullmatch(span_id)
                            or span_id.lower() == "0" * 16):
                        _deny("capture has invalid recorded span identity")
                    normalized = trace_id.lower()
                    if recorded_trace_id is None:
                        recorded_trace_id = normalized
                    if normalized != recorded_trace_id:
                        _deny("capture includes spans from unrelated trace IDs")
                    span_key = span_id.lower()
                    if span_key in recorded_span_ids:
                        _deny("capture includes duplicate or replayed span IDs")
                    recorded_span_ids.add(span_key)
        resources.extend(groups)
        if len(resources) > 100:
            _deny("assembled OTLP resource group count exceeds importer limit")
    if not recorded_span_ids:
        _deny("cannot treat an empty capture as a complete trace")
    return {"resourceSpans": resources}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--policy-suite", required=True, type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--expected", required=True, choices=("allow", "deny"))
    args = parser.parse_args()
    try:
        declared = load_json_document(args.manifest)
        merged = assemble_declared_capture(args.capture_dir, declared)
        policy = load_suite(args.policy_suite)["policy"]
        suite = import_otlp(
            merged, policy=policy, case_id=args.case_id, expected=args.expected,
        )
        print(json.dumps({
            "status": "SELF_DECLARED_LOCAL_BATCH_SET_VALIDATED",
            "declared_batch_count": declared["expected_batch_count"],
            "recorded_tool_call_count": len(suite["cases"][0]["trace"]),
            "end_of_trace_authenticated": False,
            "user_authorization_authenticated": False,
            "recorded_actions_executed": False,
        }, sort_keys=True))
        return 0
    except (SuiteError, OSError, UnicodeError, ValueError, RecursionError) as exc:
        # Do not disclose private paths, object keys, tool arguments or
        # underlying JSON parser data from untrusted capture folders.
        print(json.dumps({
            "status": "NOT_VERIFIED",
            "error_type": type(exc).__name__,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
