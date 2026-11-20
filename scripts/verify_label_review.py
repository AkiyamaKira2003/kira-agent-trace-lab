"""Audit independently authored scenario annotations WITHOUT claiming user consent.

The research manifest carries source hashes, step-label counts, and explicit
abstention for human-grant claims. Network verification is *opt in* and only
contacts two source paths under the pinned, allowlisted AgentDrift repository.
Raw source records are read into memory for comparison, never emitted.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib import request


UPSTREAM = "https://github.com/Asif-0209/AgentDrift"
RAW_UPSTREAM = "https://raw.githubusercontent.com/Asif-0209/AgentDrift"
STEP_LABELS = ("benign", "injection_point", "hijacked", "failed_injection")
MAX_DOCUMENT = 65536
MAX_SOURCE_BYTES = 16384


def _is_hash(value: Any, width: int) -> bool:
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{width}}}", value) is not None


def infer_scenario_label(counts: dict[str, int]) -> str:
    """Scenario annotation only; never assert real-world authorization."""
    total = sum(counts.values())
    if counts["hijacked"] > 0:
        return "deny"
    if total > 0 and counts["benign"] == total:
        return "allow"
    return "abstain"


def validate_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "description", "upstream_repository",
        "upstream_revision", "dataset_license", "cases",
    }:
        raise ValueError("invalid research manifest structure")
    if (value["schema_version"] != "research-label-review-1"
            or value["upstream_repository"] != UPSTREAM
            or not _is_hash(value["upstream_revision"], 40)
            or value["dataset_license"] != "CC-BY-4.0"):
        raise ValueError("unrecognized research source, version or rights")
    if not isinstance(value["description"], str) or not value["description"].strip():
        raise ValueError("missing scope description")
    cases = value["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 20:
        raise ValueError("case count must be between 1 and 20")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for case in cases:
        required = {
            "id", "source_path", "source_sha256", "origin", "author_step_counts",
            "scenario_label", "scenario_basis", "human_authorization_label",
            "human_authorization_evidence", "eligible_for_verified_authorization_metrics",
        }
        if not isinstance(case, dict) or set(case) != required:
            raise ValueError("invalid case evidence fields")
        if not isinstance(case["id"], str) or not re.fullmatch(r"[a-z0-9_]{3,80}", case["id"]):
            raise ValueError("invalid case identifier")
        if case["id"] in seen_ids:
            raise ValueError("duplicate case identifier")
        seen_ids.add(case["id"])
        path = case["source_path"]
        if not isinstance(path, str) or not re.fullmatch(r"data/test/test_[0-9]{5}\.json", path):
            raise ValueError("source path must be a bounded pinned test record")
        if path in seen_paths:
            raise ValueError("duplicate source path")
        seen_paths.add(path)
        if not _is_hash(case["source_sha256"], 64):
            raise ValueError("invalid source SHA-256")
        if case["origin"] != "third_party_synthetic":
            raise ValueError("source is not authenticated as a real user interaction")
        counts = case["author_step_counts"]
        if (not isinstance(counts, dict) or set(counts) != set(STEP_LABELS)
                or any(type(v) is not int or not 0 <= v <= 500 for v in counts.values())
                or not 1 <= sum(counts.values()) <= 500):
            raise ValueError("invalid step counts")
        if case["scenario_label"] != infer_scenario_label(counts):
            raise ValueError("scenario label conflicts with author step labels")
        if not isinstance(case["scenario_basis"], str) or len(case["scenario_basis"].strip()) < 12:
            raise ValueError("scenario annotation needs a documented rationale")
        if (case["human_authorization_label"] != "abstain"
                or case["human_authorization_evidence"] != "not_provided"
                or case["eligible_for_verified_authorization_metrics"] is not False):
            raise ValueError("synthetic benchmark records cannot authenticate human grants")
    return value


def verify_upstream_case(case: dict[str, Any], revision: str) -> None:
    """Compare exact bytes and author labels, ignoring all untrusted source prose."""
    url = f"{RAW_UPSTREAM}/{revision}/{case['source_path']}"
    req = request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "KiraAgentTraceLab-EvidenceAudit/1.0",
    })
    with request.urlopen(req, timeout=15) as response:
        raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("source record exceeds 16 KiB")
    if hashlib.sha256(raw).hexdigest() != case["source_sha256"]:
        raise ValueError("upstream record bytes differ from the pinned digest")
    record = json.loads(raw)
    if not isinstance(record, dict) or record.get("id") != case["id"]:
        raise ValueError("pinned record identity mismatch")
    steps = record.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 500:
        raise ValueError("upstream steps missing or malformed")
    if any(not isinstance(step, dict) for step in steps):
        raise ValueError("upstream step is not an object")
    labels = Counter(step.get("label") for step in steps)
    if dict(labels) != {label: count for label, count in case["author_step_counts"].items() if count}:
        raise ValueError("independent author step annotations differ from manifest")


def summary(manifest: dict[str, Any], upstream_checked: bool) -> dict[str, Any]:
    counts = Counter(case["scenario_label"] for case in manifest["cases"])
    return {
        "status": "RESEARCH_LABEL_EVIDENCE_VALIDATED",
        "source": manifest["upstream_repository"],
        "revision": manifest["upstream_revision"],
        "origin": "third_party_synthetic",
        "scenario_counts": dict(sorted(counts.items())),
        "sources_independently_retrieved": len(manifest["cases"]) if upstream_checked else 0,
        "human_authorization_verified": 0,
        "human_authorization_abstained": len(manifest["cases"]),
        "eligible_for_verified_authorization_metrics": 0,
        "tool_calls_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="reviewed metadata manifest (no raw conversations)")
    parser.add_argument("--check-upstream", action="store_true", help="opt-in pinned GitHub record-hash/label checks")
    args = parser.parse_args()
    try:
        if args.manifest.stat().st_size > MAX_DOCUMENT:
            raise ValueError("manifest exceeds 64 KiB")
        manifest = validate_manifest(json.loads(args.manifest.read_text(encoding="utf-8")))
        if args.check_upstream:
            for case in manifest["cases"]:
                verify_upstream_case(case, manifest["upstream_revision"])
        result = summary(manifest, args.check_upstream)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        # Deliberately never echo raw source content, authorization grants or tool args.
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
