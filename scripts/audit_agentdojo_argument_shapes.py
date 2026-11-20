"""Privacy-minimized top-level argument shape inventory for pinned AgentDojo runs.

The run files are untrusted data: never execute actions, print argument values,
retain arbitrary argument keys or infer consent. Offline validation is default.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent_trace_lab.schema import SuiteError
from scripts.audit_agentdojo_sampling import _parse_json
from scripts.audit_agentdojo_strata import (
    ROOT, SPEC_PATH, MANIFEST_PATH, MAX_MANIFEST, MAX_METADATA,
    MAX_FILE, MAX_TOTAL, _read_json_bounded, _fetch_limited,
    validate_spec, validate_manifest, extract_run_summary,
)

OUTPUT = ROOT / "docs" / "agentdojo_argument_shapes.json"
OUTPUT_CAP = 32768
MAX_FIELDS_PER_CALL = 32
MAX_ACTIONS = 500

# Only known, nonsecret API parameter names may be retained. Unknown strings
# (including emails or account IDs inserted as JSON keys) are NEVER copied.
SAFE_NAMES = frozenset({
    "file_path", "file_name", "file_id", "path", "query", "n", "url",
    "recipient", "recipients", "sender", "amount", "subject", "date",
    "channel", "body", "message", "message_id", "text", "content",
    "hotel_names", "hotel_name", "hotel", "start_day", "end_day",
    "day", "start_time", "end_time", "title", "location",
    "calendar_id", "event_id", "destination", "account", "currency",
    "name", "limit", "search_query", "email", "address",
})
TYPES = frozenset({"null", "boolean", "number", "string", "array", "object"})
REDACTED_KEY = "unlisted_name"


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) in (float, int):
        return "number"
    if type(value) is str:
        return "string"
    if type(value) is list:
        return "array"
    if type(value) is dict:
        return "object"
    raise SuiteError("unsupported JSON value type")


def summarize_arguments(args: Any) -> list[dict[str, str]]:
    if not isinstance(args, dict) or len(args) > MAX_FIELDS_PER_CALL:
        raise SuiteError("recorded argument object malformed or exceeds field cap")
    if not all(isinstance(key, str) for key in args):
        raise SuiteError("recorded argument key must be string")
    # Raw keys are used for deterministic iteration only, never emitted.
    return [
        {"name": key if key in SAFE_NAMES else REDACTED_KEY, "type": json_type(args[key])}
        for key in sorted(args)
    ]


def summarize_run(slot: dict[str, Any], payload: bytes) -> list[dict[str, Any]]:
    envelope = extract_run_summary(slot, payload)
    run = _parse_json(payload)
    if not isinstance(run, dict):
        raise SuiteError("source run must be a JSON object")
    out = []
    for msg in run["messages"]:
        if not isinstance(msg, dict):
            raise SuiteError("source message malformed")
        for call in msg.get("tool_calls") or []:
            if not isinstance(call, dict):
                raise SuiteError("source call malformed")
            out.append({
                "action_id": f"slot_{slot['slot_index']:02d}:action_{len(out):03d}",
                "tool": call["function"],
                "argument_shape": summarize_arguments(call["args"]),
            })
    if len(out) > MAX_ACTIONS or [call["tool"] for call in out] != envelope["observed_tools"]:
        raise SuiteError("source action names/order not reproducible")
    return out


def inventory_from_upstream(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    total = 0
    records = []
    for i, original in enumerate(manifest["records"]):
        entry = {
            "slot_id": f"slot_{i:02d}",
            "source_path": original["source_path"],
            "status": original["status"],
            "source_sha256": original["sha256"],
            "actions": [],
            "simulated_action_authorization": "abstain",
            "human_authorization": "abstain",
        }
        if original["status"] == "present":
            status, raw = _fetch_limited(original["source_path"], MAX_FILE)
            if status != "present":
                raise SuiteError("expected pinned record unavailable or oversized")
            total += len(raw)
            if total > MAX_TOTAL or hashlib.sha256(raw).hexdigest() != original["sha256"]:
                raise SuiteError("upstream byte source differs from pinned recorded run")
            observed = summarize_run({**original, "slot_index": i}, raw)
            if [x["tool"] for x in observed] != original["observed_tools"]:
                raise SuiteError("source calls differ from pinned exposure sequence")
            entry["actions"] = observed
        elif original["status"] != "missing":
            # No unexpected partial/malformed statuses in this frozen study.
            raise SuiteError("unknown source status in pinned study")
        records.append(entry)
    return records


def validate_inventory(manifest: dict[str, Any], value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "source_revision", "preregistration_commit", "data_policy",
        "records", "accepted_independent_reviewers",
    } or value["schema_version"] != "agentdojo-argument-shapes-1":
        raise SuiteError("invalid argument inventory envelope")
    if (value["source_revision"] != manifest["source_revision"]
            or value["preregistration_commit"] != manifest["preregistration_commit"]
            or value["data_policy"] != "allowed_top_level_argument_names_and_types_only"
            or value["accepted_independent_reviewers"] != []):
        raise SuiteError("argument inventory provenance or consent changed")
    rows = value["records"]
    if not isinstance(rows, list) or len(rows) != 24:
        raise SuiteError("24-slot denominator not preserved")
    for i, (row, original) in enumerate(zip(rows, manifest["records"])):
        if not isinstance(row, dict) or set(row) != {
            "slot_id", "source_path", "status", "source_sha256", "actions",
            "simulated_action_authorization", "human_authorization",
        }:
            raise SuiteError("argument inventory slot schema mismatch")
        if (row["slot_id"] != f"slot_{i:02d}"
                or row["source_path"] != original["source_path"]
                or row["status"] != original["status"]
                or row["source_sha256"] != original["sha256"]
                or row["simulated_action_authorization"] != "abstain"
                or row["human_authorization"] != "abstain"):
            raise SuiteError("slot identity, source hash or authorization label altered")
        actions = row["actions"]
        if not isinstance(actions, list) or len(actions) != (
                len(original["observed_tools"]) if original["status"] == "present" else 0):
            raise SuiteError("source action count differs or missing row filled")
        for j, action in enumerate(actions):
            if not isinstance(action, dict) or set(action) != {
                "action_id", "tool", "argument_shape",
            } or action["action_id"] != f"slot_{i:02d}:action_{j:03d}" or action["tool"] != original["observed_tools"][j]:
                raise SuiteError("recorded action identity/name altered")
            shape = action["argument_shape"]
            if not isinstance(shape, list) or len(shape) > MAX_FIELDS_PER_CALL:
                raise SuiteError("argument field inventory malformed")
            for field in shape:
                if (not isinstance(field, dict) or set(field) != {"name", "type"}
                        or field["name"] not in SAFE_NAMES | {REDACTED_KEY}
                        or field["type"] not in TYPES):
                    raise SuiteError("unsafe field name/type in committed inventory")
    return value


def report(value: dict[str, Any], online: bool) -> dict[str, Any]:
    rows = value["records"]
    return {
        "status": "PINNED_ARGUMENT_SHAPES_VERIFIED" if online else "OFFLINE_ARGUMENT_SHAPES_VALIDATED",
        "slots": len(rows),
        "present": sum(row["status"] == "present" for row in rows),
        "missing": sum(row["status"] == "missing" for row in rows),
        "actions": sum(len(row["actions"]) for row in rows),
        "unknown_name_fields_redacted": sum(
            field["name"] == REDACTED_KEY for row in rows for action in row["actions"]
            for field in action["argument_shape"]
        ),
        "actual_argument_values_stored": False,
        "accepted_independent_authorization_labels": 0,
        "recorded_actions_executed": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--capture-upstream", action="store_true",
                      help="one-time hash-pinned read of present runs and exclusive output creation")
    mode.add_argument("--check-upstream", action="store_true",
                      help="compare fixed source byte hashes and redacted shapes to committed output")
    args = parser.parse_args()
    try:
        spec = validate_spec(_read_json_bounded(SPEC_PATH, MAX_METADATA))
        exposure = validate_manifest(spec, _read_json_bounded(MANIFEST_PATH, MAX_MANIFEST))
        if args.capture_upstream:
            if OUTPUT.exists():
                raise SuiteError("do not overwrite a captured source inventory")
            value = {
                "schema_version": "agentdojo-argument-shapes-1",
                "source_revision": exposure["source_revision"],
                "preregistration_commit": exposure["preregistration_commit"],
                "data_policy": "allowed_top_level_argument_names_and_types_only",
                "records": inventory_from_upstream(exposure),
                "accepted_independent_reviewers": [],
            }
            validate_inventory(exposure, value)
            data = (json.dumps(value, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
            if len(data) > OUTPUT_CAP:
                raise SuiteError("redacted inventory exceeds metadata cap")
            with OUTPUT.open("xb") as f:
                f.write(data)
        value = validate_inventory(exposure, _read_json_bounded(OUTPUT, OUTPUT_CAP))
        if args.check_upstream and inventory_from_upstream(exposure) != value["records"]:
            raise SuiteError("upstream shapes differ from committed evidence")
        print(json.dumps(report(value, args.capture_upstream or args.check_upstream), sort_keys=True))
    except (OSError, ValueError, UnicodeError, RecursionError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
