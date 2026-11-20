"""Reproduce a deterministic two-suite AgentDojo sampling *exposure* protocol.

No policy verdicts or human authorization labels are inferred. The default
mode validates metadata offline. --check-upstream reads only one bounded GitHub
directory listing and four byte-hash-pinned public recorded runs; recorded
tool arguments and all messages remain in memory, never printed or saved.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any
from urllib import request

from agent_trace_lab.schema import SuiteError, _object_no_duplicates, _reject_non_json_number
from scripts.verify_agentdojo_simulated_boundary import fetch_pinned


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "agentdojo_sampling_manifest.json"
REPOSITORY = "https://github.com/ethz-spylab/agentdojo"
REVISION = "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
RUN_ROOT = "runs/gpt-4o-2024-05-13"
RULE = "lexicographic_suite_endpoints__fixed_user_task_0__two_fixed_conditions"
SUITES = ["banking", "slack", "travel", "workspace"]
CONDITIONS = ["no_injection", "injection_attempt"]
MAX_MANIFEST = 16384
MAX_SOURCE_RUN = 16384
MAX_LISTING = 16384


def _selected_from_suites(suites: list[str]) -> list[str]:
    if len(suites) < 2 or len(suites) != len(set(suites)) or suites != sorted(suites):
        raise SuiteError("suite list must be sorted, unique and have two or more members")
    return [suites[0], suites[-1]]


def _source_path(suite: str, condition: str) -> str:
    suffix = {
        "no_injection": "none/none.json",
        "injection_attempt": "important_instructions/injection_task_0.json",
    }[condition]
    return f"{RUN_ROOT}/{suite}/user_task_0/{suffix}"


def validate_manifest(obj: Any) -> dict[str, Any]:
    required = {
        "schema_version", "upstream_repository", "revision", "repository_license",
        "model_run_root", "available_suites", "selected_suites", "selection_rule",
        "conditions", "records",
    }
    if not isinstance(obj, dict) or set(obj) != required:
        raise SuiteError("sampling manifest fields are malformed")
    if (obj["schema_version"] != "agentdojo-sampling-1"
            or obj["upstream_repository"] != REPOSITORY or obj["revision"] != REVISION
            or obj["repository_license"] != "MIT" or obj["model_run_root"] != RUN_ROOT
            or obj["selection_rule"] != RULE):
        raise SuiteError("sampling source and predeclared rule are not pinned")
    # Compare with the previously inspected upstream run-root listing. During
    # upstream verification the actual pinned directory is read and compared.
    if obj["available_suites"] != SUITES:
        raise SuiteError("upstream suite universe differs from reviewed snapshot")
    selected = _selected_from_suites(obj["available_suites"])
    if obj["selected_suites"] != selected or obj["conditions"] != CONDITIONS:
        raise SuiteError("sample was selected outside the fixed source-derived rule")
    records = obj["records"]
    if not isinstance(records, list) or len(records) != 4:
        raise SuiteError("sampling protocol requires four balanced records")
    expected_pairs = [(suite, condition) for suite in selected for condition in CONDITIONS]
    for index, ((suite, condition), record) in enumerate(zip(expected_pairs, records)):
        location = f"records[{index}]"
        required_record = {
            "suite", "condition", "source_path", "sha256", "observed_tools",
            "publisher_utility", "publisher_security_field",
            "simulated_authorization_label", "real_human_authorization_label",
        }
        if not isinstance(record, dict) or set(record) != required_record:
            raise SuiteError(f"{location}: unexpected fields")
        if (record["suite"], record["condition"]) != (suite, condition):
            raise SuiteError(f"{location}: incorrect source selection or cohort")
        if record["source_path"] != _source_path(suite, condition):
            raise SuiteError(f"{location}: noncanonical run path")
        digest = record["sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise SuiteError(f"{location}: pinned source hash missing or malformed")
        names = record["observed_tools"]
        if (not isinstance(names, list) or not 1 <= len(names) <= 1000
                or any(not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", name) is None
                       for name in names)):
            raise SuiteError(f"{location}: malformed observed tool names")
        if type(record["publisher_utility"]) is not bool or type(record["publisher_security_field"]) is not bool:
            raise SuiteError(f"{location}: publisher outcome flags must be booleans")
        if (record["simulated_authorization_label"] != "abstain"
                or record["real_human_authorization_label"] != "abstain"):
            raise SuiteError(f"{location}: exposure does not prove consent or simulated policy scope")
    return obj


def _parse_json(raw: bytes) -> Any:
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_object_no_duplicates,
        parse_constant=_reject_non_json_number,
    )


def check_directory(suite_names: Any) -> None:
    if not isinstance(suite_names, list) or suite_names != SUITES:
        raise SuiteError("source run-root suites changed or are not in reviewed order")
    if _selected_from_suites(suite_names) != ["banking", "workspace"]:
        raise SuiteError("lexicographic endpoint selection changed")


def check_run(record: dict[str, Any], run: Any) -> None:
    if not isinstance(run, dict):
        raise SuiteError("upstream record is not an object")
    injected = record["condition"] == "injection_attempt"
    if (run.get("suite_name") != record["suite"] or run.get("user_task_id") != "user_task_0"
            or run.get("injection_task_id") != ("injection_task_0" if injected else None)
            or run.get("attack_type") != ("important_instructions" if injected else None)
            or run.get("error") is not None
            or run.get("utility") is not record["publisher_utility"]
            or run.get("security") is not record["publisher_security_field"]):
        raise SuiteError("upstream run identity, cohort or publisher fields disagree")
    messages = run.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 100:
        raise SuiteError("upstream recorded messages absent or excessive")
    observed: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            raise SuiteError("upstream message malformed")
        calls = message.get("tool_calls")
        if calls is None:
            continue
        if not isinstance(calls, list):
            raise SuiteError("upstream tool_calls malformed")
        if calls and message.get("role") != "assistant":
            raise SuiteError("upstream non-assistant tool_calls cannot be sampled")
        for call in calls:
            if (not isinstance(call, dict) or not isinstance(call.get("function"), str)
                    or not isinstance(call.get("args"), dict)
                    or not isinstance(call.get("id"), str)):
                raise SuiteError("upstream function-call envelope changed")
            observed.append(call["function"])
    if observed != record["observed_tools"]:
        raise SuiteError("upstream ordered action names differ from pinned manifest")


def verify_upstream(manifest: dict[str, Any]) -> None:
    url = (f"https://api.github.com/repos/ethz-spylab/agentdojo/contents/"
           f"{RUN_ROOT}?ref={REVISION}")
    req = request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "KiraAgentTraceLab-SamplingAudit/1.0",
    })
    with request.urlopen(req, timeout=15) as response:
        payload = response.read(MAX_LISTING + 1)
    if len(payload) > MAX_LISTING:
        raise SuiteError("source suite directory listing exceeds transfer limit")
    entries = _parse_json(payload)
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise SuiteError("invalid pinned suite directory listing")
    actual_suites = sorted(e["name"] for e in entries if e.get("type") == "dir" and isinstance(e.get("name"), str))
    check_directory(actual_suites)
    for record in manifest["records"]:
        raw = fetch_pinned(REVISION, record["source_path"], record["sha256"], MAX_SOURCE_RUN)
        check_run(record, _parse_json(raw))


def report(manifest: dict[str, Any], upstream_verified: bool) -> dict[str, Any]:
    cohorts = Counter(row["condition"] for row in manifest["records"])
    families = Counter(row["suite"] for row in manifest["records"])
    return {
        "status": ("PINNED_SAMPLING_EXPOSURES_VERIFIED" if upstream_verified
                   else "OFFLINE_SAMPLING_MANIFEST_VALIDATED"),
        "source_revision": REVISION,
        "selection_rule": RULE,
        "source_families": dict(sorted(families.items())),
        "exposure_cohorts": dict(sorted(cohorts.items())),
        "observed_tool_call_counts": [
            {"family": row["suite"], "condition": row["condition"], "count": len(row["observed_tools"])}
            for row in manifest["records"]
        ],
        "source_files_hash_verified": len(manifest["records"]) if upstream_verified else 0,
        "source_suite_listing_checked": upstream_verified,
        "simulated_scope_abstentions": len(manifest["records"]),
        "human_authorization_abstentions": len(manifest["records"]),
        "policy_verdicts_computed": 0,
        "population_accuracy_claimed": False,
        "recorded_actions_executed": False,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-upstream", action="store_true",
                        help="explicitly fetch pinned public suite listing + 4 bounded run files")
    args = parser.parse_args()
    try:
        if MANIFEST_PATH.stat().st_size > MAX_MANIFEST:
            raise SuiteError("manifest exceeds 16KiB limit")
        manifest = validate_manifest(_parse_json(MANIFEST_PATH.read_bytes()))
        if args.check_upstream:
            verify_upstream(manifest)
        result = report(manifest, args.check_upstream)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
