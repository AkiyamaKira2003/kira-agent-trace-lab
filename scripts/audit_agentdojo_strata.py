"""Pre-registered multi-suite AgentDojo exposures; no tool execution or consent claims.

Offline is the default; --capture-upstream writes ONLY a summary of the 24
predeclared slots. --check-upstream verifies all paths again against the frozen
GitHub revision, with a bounded total transfer budget. Never print/save any
recorded message, tool arguments, recipient, financial detail, or model text.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib import error, request

from agent_trace_lab.schema import SuiteError
from scripts.audit_agentdojo_sampling import _parse_json

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "docs" / "agentdojo_stratified_preregistration.json"
MANIFEST_PATH = ROOT / "docs" / "agentdojo_stratified_exposures.json"
PREREG_COMMIT = "3385f7db5227400cc14caa995b0a9054b3a995f7"
SOURCE_REV = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
REPO = "https://github.com/ethz-spylab/agentdojo"
RUN_ROOT = "runs/gpt-4o-2024-05-13"
SUITES = ["banking", "slack", "travel", "workspace"]
TASK_INDICES = [0, 1]
CONDITIONS = [
    ("baseline", "none/none.json", None),
    ("direct", "direct/injection_task_0.json", "direct"),
    ("important_instructions", "important_instructions/injection_task_0.json", "important_instructions"),
]
MAX_FILE = 65536
MAX_TOTAL = 1572864
MAX_MANIFEST = 32768
MAX_METADATA = 32768
MAX_FETCHES = 24
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
TOOL_RE = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")


def _read_json_bounded(path: Path, max_size: int) -> Any:
    if path.stat().st_size > max_size:
        raise SuiteError("metadata file exceeds preregistered size cap")
    return _parse_json(path.read_bytes())


def validate_spec(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, dict) or set(spec) != {
        "schema_version", "study_id", "upstream_repository", "revision",
        "license", "run_root", "suite_universe", "suite_selection",
        "task_indices", "conditions", "ordering", "expected_slots",
        "missing_or_oversize", "max_file_bytes", "max_source_downloads",
        "max_source_total_bytes", "max_metadata_bytes", "selection_ignores",
        "research_goal",
    }:
        raise SuiteError("invalid preregistration schema")
    anchors = {
        "schema_version": "agentdojo-strata-preregistration-1",
        "study_id": "ATL-004G-2026-11-21",
        "upstream_repository": REPO, "revision": SOURCE_REV,
        "license": "MIT", "run_root": RUN_ROOT,
        "suite_universe": SUITES, "suite_selection": "all_four_source_suites",
        "task_indices": TASK_INDICES, "ordering": "suite_lexicographic_then_task_ascending_then_condition_list",
        "expected_slots": 24,
        "missing_or_oversize": "record_explicitly_as_missing_or_oversize_never_substitute",
        "max_file_bytes": MAX_FILE, "max_source_downloads": MAX_FETCHES,
        "max_source_total_bytes": MAX_TOTAL, "max_metadata_bytes": MAX_METADATA,
        "selection_ignores": [
            "publisher_utility", "publisher_security", "policy_verdicts", "reviewer_labels",
        ],
        "research_goal": "metadata-only study of tool-call exposures and review feasibility; no population generalization",
    }
    if any(type(spec[k]) is not type(v) or spec[k] != v for k, v in anchors.items()):
        raise SuiteError("changed precommitted source-selection rule")
    expect_conditions = [
        {"id": name, "relative_path": rel, "attack_type": attack,
         "injection_task_id": "injection_task_0" if attack else None}
        for name, rel, attack in CONDITIONS
    ]
    if spec["conditions"] != expect_conditions:
        raise SuiteError("changed preregistered exposure conditions")
    return spec


def planned_slots(spec: dict[str, Any]) -> list[dict[str, Any]]:
    # Exact cartesian product and order. Not a convenience lookup from observed outcomes.
    slots = [
        {"suite": suite, "task_index": task, "condition": condition,
         "source_path": f"{RUN_ROOT}/{suite}/user_task_{task}/{rel}"}
        for suite in spec["suite_universe"]
        for task in spec["task_indices"]
        for condition, rel, _ in CONDITIONS
    ]
    if len(slots) != MAX_FETCHES or len({row["source_path"] for row in slots}) != MAX_FETCHES:
        raise SuiteError("precommitted cartesian product is not 24 unique paths")
    return slots


def extract_run_summary(slot: dict[str, Any], payload: bytes) -> dict[str, Any]:
    run = _parse_json(payload)
    if not isinstance(run, dict):
        raise SuiteError("source run is not an object")
    name = slot["condition"]
    attack_name = None if name == "baseline" else name
    if (run.get("suite_name") != slot["suite"]
            or run.get("user_task_id") != f"user_task_{slot['task_index']}"
            or run.get("attack_type") != attack_name
            or run.get("injection_task_id") != (None if name == "baseline" else "injection_task_0")):
        raise SuiteError("recorded suite/task/injection mismatch")
    # Flags are publisher metadata only; never used to select or label an action.
    utility, security = run.get("utility"), run.get("security")
    if type(utility) is not bool or type(security) is not bool:
        raise SuiteError("publisher flags are not booleans")
    msgs = run.get("messages")
    if not isinstance(msgs, list) or not 1 <= len(msgs) <= 200:
        raise SuiteError("recorded message count out of bounds")
    names = []
    for msg in msgs:
        if not isinstance(msg, dict):
            raise SuiteError("recorded message envelope malformed")
        calls = msg.get("tool_calls")
        if calls is None:
            continue
        if not isinstance(calls, list) or len(calls) > 100:
            raise SuiteError("tool call list malformed or too large")
        if calls and msg.get("role") != "assistant":
            raise SuiteError("tool calls must belong to assistant")
        for call in calls:
            if (not isinstance(call, dict) or not isinstance(call.get("id"), str)
                    or not isinstance(call.get("args"), dict)
                    or not isinstance(call.get("function"), str)
                    or TOOL_RE.fullmatch(call["function"]) is None):
                raise SuiteError("recorded function call invalid")
            names.append(call["function"])
    if len(names) > 500:
        raise SuiteError("too many recorded actions")
    return {"observed_tools": names, "publisher_utility": utility,
            "publisher_security_field": security, "source_error_present": run.get("error") is not None}


def _fetch_limited(path: str, per_file_cap: int) -> tuple[str, bytes]:
    url = f"https://raw.githubusercontent.com/ethz-spylab/agentdojo/{SOURCE_REV}/{path}"
    req = request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "KiraAgentTraceLab-StratifiedReadOnlyAudit/1.0",
    })
    try:
        with request.urlopen(req, timeout=15) as resp:
            data = resp.read(per_file_cap + 1)
    except error.HTTPError as exc:
        if exc.code == 404:
            return ("missing", b"")
        raise
    if len(data) > per_file_cap:
        return ("oversize", b"")
    return ("present", data)


def gather(spec: dict[str, Any]) -> list[dict[str, Any]]:
    total_received = 0
    rows = []
    for slot in planned_slots(spec):
        # Fail closed on transient network errors; do not conceal them as missing.
        status, payload = _fetch_limited(slot["source_path"], MAX_FILE)
        total_received += len(payload) if status == "present" else (MAX_FILE + 1 if status == "oversize" else 0)
        if total_received > MAX_TOTAL:
            raise SuiteError("sample exceeds preregistered total transfer budget")
        row: dict[str, Any] = dict(slot)
        row["status"] = status
        row["sha256"] = hashlib.sha256(payload).hexdigest() if status == "present" else None
        row["size_bytes"] = len(payload) if status == "present" else None
        row["observed_tools"] = []
        row["publisher_utility"] = None
        row["publisher_security_field"] = None
        row["source_error_present"] = None
        if status == "present":
            try:
                row.update(extract_run_summary(slot, payload))
            except (ValueError, UnicodeError, RecursionError):
                row["status"] = "malformed"
        row["simulated_scope_review"] = "not_reviewed"
        row["real_human_authorization_label"] = "abstain"
        rows.append(row)
    return rows


def validate_manifest(spec: dict[str, Any], manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version", "preregistration_commit", "source_revision", "records",
        "independent_reviewers", "adjudication_state",
    }:
        raise SuiteError("stratified manifest schema mismatch")
    if (manifest["schema_version"] != "agentdojo-strata-exposures-1"
            or manifest["preregistration_commit"] != PREREG_COMMIT
            or manifest["source_revision"] != SOURCE_REV
            or manifest["independent_reviewers"] != []
            or manifest["adjudication_state"] != "not_started"):
        raise SuiteError("pre-registration, provenance or reviewer claims changed")
    expected = planned_slots(spec)
    records = manifest["records"]
    if not isinstance(records, list) or len(records) != len(expected):
        raise SuiteError("sampling row denominator changed")
    keys = {
        "suite", "task_index", "condition", "source_path", "status", "sha256",
        "size_bytes", "observed_tools", "publisher_utility", "publisher_security_field",
        "source_error_present", "simulated_scope_review", "real_human_authorization_label",
    }
    for index, (slot, row) in enumerate(zip(expected, records)):
        if not isinstance(row, dict) or set(row) != keys:
            raise SuiteError(f"record {index} fields invalid")
        if any(type(row[k]) is not type(v) or row[k] != v for k, v in slot.items()):
            raise SuiteError(f"record {index} violates preregistered path/order")
        if (row["real_human_authorization_label"] != "abstain"
                or row["simulated_scope_review"] != "not_reviewed"):
            raise SuiteError(f"record {index} cannot claim external grants or reviewers")
        if row["status"] not in ("present", "missing", "oversize", "malformed"):
            raise SuiteError(f"record {index} unknown availability state")
        if row["status"] in ("present", "malformed"):
            if (not isinstance(row["sha256"], str) or SHA_RE.fullmatch(row["sha256"]) is None
                    or type(row["size_bytes"]) is not int or not 0 < row["size_bytes"] <= MAX_FILE):
                raise SuiteError(f"record {index} missing source fingerprints")
        elif row["sha256"] is not None or row["size_bytes"] is not None:
            raise SuiteError(f"record {index} must not invent source hash")
        if not isinstance(row["observed_tools"], list) or len(row["observed_tools"]) > 500 or any(
            not isinstance(tool, str) or TOOL_RE.fullmatch(tool) is None
            for tool in row["observed_tools"]
        ):
            raise SuiteError(f"record {index} malformed tool summary")
        if row["status"] == "present":
            if (type(row["publisher_utility"]) is not bool
                    or type(row["publisher_security_field"]) is not bool
                    or type(row["source_error_present"]) is not bool):
                raise SuiteError(f"record {index} publisher summary malformed")
        elif (row["observed_tools"] or row["publisher_utility"] is not None
                or row["publisher_security_field"] is not None
                or row["source_error_present"] is not None):
            raise SuiteError(f"record {index} fabricates missing/malformed evidence")
    return manifest


def verify_upstream(spec: dict[str, Any], manifest: dict[str, Any]) -> None:
    refreshed = gather(spec)
    # Exact metadata equality, including SHA and ordered tool list, not merely existence.
    if refreshed != manifest["records"]:
        raise SuiteError("upstream byte hash, action sequence or availability differs")


def report(spec: dict[str, Any], manifest: dict[str, Any], online: bool,
           capture: bool = False) -> dict[str, Any]:
    rows = manifest["records"]
    return {
        "status": ("UPSTREAM_24_SLOTS_CAPTURED" if capture
                   else "UPSTREAM_24_SLOTS_VERIFIED" if online
                   else "OFFLINE_24_SLOTS_VALIDATED"),
        "preregistration_commit": PREREG_COMMIT,
        "source_revision": SOURCE_REV,
        "planned_slots": len(planned_slots(spec)),
        "suite_counts": dict(sorted(Counter(r["suite"] for r in rows).items())),
        "condition_counts": dict(sorted(Counter(r["condition"] for r in rows).items())),
        "availability": dict(sorted(Counter(r["status"] for r in rows).items())),
        "readable_run_hashes_rechecked": (sum(r["status"] in ("present", "malformed")
                                             for r in rows) if online and not capture else 0),
        "simulated_scope_reviews_completed": 0,
        "simulated_scope_reviews_pending": len(rows),
        "real_human_grant_abstentions": len(rows),
        "independent_reviewers": 0,
        "policy_verdicts_computed": 0,
        "population_accuracy_claimed": False,
        "recorded_actions_executed": False,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--capture-upstream", action="store_true",
                       help="read 24 preregistered public paths and write safe metadata-only manifest")
    group.add_argument("--check-upstream", action="store_true",
                       help="verify all 24 source slots against committed metadata")
    args = parser.parse_args()
    try:
        spec = validate_spec(_read_json_bounded(SPEC_PATH, MAX_METADATA))
        if args.capture_upstream:
            if MANIFEST_PATH.exists():
                raise SuiteError("existing evidence cannot be overwritten by --capture-upstream")
            result = {
                "schema_version": "agentdojo-strata-exposures-1",
                "preregistration_commit": PREREG_COMMIT,
                "source_revision": SOURCE_REV,
                "records": gather(spec),
                "independent_reviewers": [],
                "adjudication_state": "not_started",
            }
            validate_manifest(spec, result)
            rendered = (json.dumps(result, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
            if len(rendered) > MAX_MANIFEST:
                raise SuiteError("metadata manifest exceeds budget; do not drop rows")
            with MANIFEST_PATH.open("xb") as output:
                output.write(rendered)
            print(json.dumps(report(spec, result, True, capture=True), sort_keys=True))
            return 0
        manifest = validate_manifest(spec, _read_json_bounded(MANIFEST_PATH, MAX_MANIFEST))
        if args.check_upstream:
            verify_upstream(spec, manifest)
        print(json.dumps(report(spec, manifest, args.check_upstream), sort_keys=True))
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
