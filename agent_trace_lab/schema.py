"""Strict, bounded JSON input contract. Traces are data, never executable code."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_CASES = 500
MAX_EVENTS = 10000
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")


class SuiteError(ValueError):
    """Invalid input; no trace actions have been performed."""


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            # JSON object keys are untrusted and may carry user secrets.
            raise SuiteError("duplicate JSON property")
        result[key] = value
    return result


def _reject_non_json_number(token: str) -> None:
    raise SuiteError(f"non-JSON numeric constant is not allowed: {token}")


def decode_json_arguments(value: Any, location: str) -> dict[str, Any]:
    """Decode an observed tool's arguments as strict JSON without executing them."""
    if isinstance(value, str):
        try:
            value = json.loads(
                value,
                object_pairs_hook=_object_no_duplicates,
                parse_constant=_reject_non_json_number,
            )
        except (json.JSONDecodeError, RecursionError) as exc:
            raise SuiteError(f"{location}: arguments must contain valid JSON object") from exc
    if not isinstance(value, dict):
        raise SuiteError(f"{location}: arguments must be a JSON object")
    return value


def _keys(value: Any, location: str, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise SuiteError(f"{location} must be a JSON object")
    actual = set(value)
    missing = required - actual
    unexpected = actual - required - (optional or set())
    if missing or unexpected:
        # Required keys come from the trusted schema; never echo unknown keys.
        raise SuiteError(
            f"{location}: missing={sorted(missing)}, unexpected_count={len(unexpected)}"
        )
    return value


def _strings(value: Any, location: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise SuiteError(f"{location} must be a {'nonempty ' if not allow_empty else ''}list")
    if len(value) > 100 or any(not isinstance(item, str) or not item for item in value):
        raise SuiteError(f"{location} must contain 1..100 nonempty strings")
    if len(value) != len(set(value)):
        raise SuiteError(f"{location} must not have duplicates")
    return value


def _canonical_path(path: str) -> bool:
    return (
        path.startswith("/")
        and not path.startswith("//")
        and "\\" not in path
        and "\x00" not in path
        and all(segment not in ("", ".", "..") for segment in path.split("/")[1:])
    ) or path == "/"


def _exact_arguments(value: Any, location: str) -> str:
    """Stable JSON encoding that distinguishes bool from int and ignores object key order."""
    if not isinstance(value, dict) or len(value) > 100:
        raise SuiteError(f"{location} must be a JSON arguments object (max 100 keys)")
    def verify_node(node: Any, depth: int) -> None:
        if depth > 32:
            raise SuiteError(f"{location} contains excessively nested values")
        if isinstance(node, dict):
            if len(node) > 100 or any(type(key) is not str for key in node):
                raise SuiteError(f"{location} contains invalid JSON object keys")
            for nested in node.values():
                verify_node(nested, depth + 1)
        elif isinstance(node, list):
            if len(node) > 1000:
                raise SuiteError(f"{location} contains an oversized list")
            for nested in node:
                verify_node(nested, depth + 1)
        elif type(node) not in (str, int, float, bool, type(None)):
            raise SuiteError(f"{location} contains unsupported JSON values")

    verify_node(value, 0)
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise SuiteError(f"{location} must contain finite, serializable JSON values") from exc


def _validate_task_authorization(case: dict[str, Any], location: str, guarded: set[str]) -> None:
    authorization = case.get("task_authorization")
    if authorization is None:
        if "task_authorization" in case:
            raise SuiteError(f"{location}.task_authorization must be an object when provided")
        return  # explicit absence means no grants; guarded calls will be denied
    authorization = _keys(authorization, f"{location}.task_authorization", {"task_id", "grants"})
    task_id = authorization["task_id"]
    if not isinstance(task_id, str) or not _IDENTIFIER.fullmatch(task_id):
        raise SuiteError(f"{location}.task_authorization.task_id is invalid")
    grants = authorization["grants"]
    if not isinstance(grants, list) or len(grants) > 100:
        raise SuiteError(f"{location}.task_authorization.grants must be a list (max 100)")
    grant_ids: set[str] = set()
    for index, grant in enumerate(grants):
        where = f"{location}.task_authorization.grants[{index}]"
        grant = _keys(grant, where, {"grant_id", "source_ref", "tool", "arguments"})
        grant_id = grant["grant_id"]
        if not isinstance(grant_id, str) or not _IDENTIFIER.fullmatch(grant_id) or grant_id in grant_ids:
            raise SuiteError(f"{where}.grant_id must be a distinct identifier")
        grant_ids.add(grant_id)
        source_ref = grant["source_ref"]
        if (
            not isinstance(source_ref, str) or not 1 <= len(source_ref) <= 240
            or not source_ref.isprintable() or source_ref != source_ref.strip()
        ):
            raise SuiteError(f"{where}.source_ref must be a nonempty printable external evidence reference")
        if not isinstance(grant["tool"], str) or grant["tool"] not in guarded:
            raise SuiteError(f"{where}.tool must be one of the guarded tools")
        _exact_arguments(grant["arguments"], f"{where}.arguments")


def validate_suite(suite: Any) -> dict[str, Any]:
    suite = _keys(suite, "suite", {"schema_version", "policy", "cases"})
    version = suite["schema_version"]
    if version not in ("1.0", "1.1"):
        raise SuiteError("unsupported schema_version (expected 1.0 or 1.1)")

    policy_required = {"tools", "max_actions"} | ({"task_guarded_tools"} if version == "1.1" else set())
    policy = _keys(suite["policy"], "policy", policy_required)
    limit = policy["max_actions"]
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise SuiteError("policy.max_actions must be an integer from 1 to 1000")
    tools = policy["tools"]
    if not isinstance(tools, dict) or not 1 <= len(tools) <= 100:
        raise SuiteError("policy.tools must be a nonempty object (max 100)")
    for tool_index, (name, config) in enumerate(tools.items()):
        tool_location = f"policy.tools[{tool_index}]"
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise SuiteError(f"{tool_location}: invalid tool name")
        config = _keys(
            config, tool_location, set(),
            {"path_args", "allowed_roots", "url_args", "allowed_hosts"},
        )
        path_args = _strings(config.get("path_args", []), f"{tool_location}.path_args")
        roots = _strings(config.get("allowed_roots", []), f"{tool_location}.allowed_roots")
        url_args = _strings(config.get("url_args", []), f"{tool_location}.url_args")
        hosts = _strings(config.get("allowed_hosts", []), f"{tool_location}.allowed_hosts")
        if bool(path_args) != bool(roots) or bool(url_args) != bool(hosts):
            raise SuiteError(f"{tool_location}: path_args/allowed_roots and url_args/allowed_hosts must be paired")
        if any(not _IDENTIFIER.fullmatch(arg) for arg in path_args + url_args):
            raise SuiteError(f"{tool_location}: invalid argument name")
        if set(path_args) & set(url_args):
            raise SuiteError(f"{tool_location}: an argument cannot be a path and URL")
        if any(not _canonical_path(root) for root in roots):
            raise SuiteError(f"{tool_location}: allowed_roots must be canonical absolute POSIX paths")
        if any(host != host.lower() or not _HOST.fullmatch(host) or ".." in host for host in hosts):
            raise SuiteError(f"{tool_location}: allowed_hosts must be exact lower-case DNS names")

    guarded: set[str] = set()
    if version == "1.1":
        guarded_list = _strings(policy["task_guarded_tools"], "policy.task_guarded_tools", allow_empty=False)
        if any(tool not in tools for tool in guarded_list):
            raise SuiteError("policy.task_guarded_tools must reference allowlisted tools")
        guarded = set(guarded_list)

    cases = suite["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise SuiteError(f"cases must contain 1..{MAX_CASES} entries")
    ids: set[str] = set()
    total_events = 0
    for index, case in enumerate(cases):
        location = f"cases[{index}]"
        optional = {"description", "task_authorization"} if version == "1.1" else {"description"}
        case = _keys(case, location, {"id", "expected", "trace"}, optional)
        case_id = case["id"]
        if not isinstance(case_id, str) or not _IDENTIFIER.fullmatch(case_id) or case_id in ids:
            raise SuiteError(f"{location}.id must be unique and use letters, digits, _ . -")
        ids.add(case_id)
        if case["expected"] not in ("allow", "deny"):
            raise SuiteError(f"{location}.expected must be allow or deny")
        if "description" in case and (not isinstance(case["description"], str) or len(case["description"]) > 500):
            raise SuiteError(f"{location}.description must be a string (max 500 characters)")
        trace = case["trace"]
        if not isinstance(trace, list) or len(trace) > 1000:
            raise SuiteError(f"{location}.trace must be a list of at most 1000 events")
        total_events += len(trace)
        if total_events > MAX_EVENTS:
            raise SuiteError(f"total events exceeds {MAX_EVENTS}")
        for event_index, event in enumerate(trace):
            where = f"{location}.trace[{event_index}]"
            event = _keys(event, where, {"tool", "arguments"})
            if not isinstance(event["tool"], str) or not _IDENTIFIER.fullmatch(event["tool"]):
                raise SuiteError(f"{where}.tool is invalid")
            arguments = event["arguments"]
            if not isinstance(arguments, dict) or len(arguments) > 100:
                raise SuiteError(f"{where}.arguments must be a JSON object (max 100 keys)")
            if any(not isinstance(k, str) or len(k) > 80 for k in arguments):
                raise SuiteError(f"{where}.arguments has invalid keys")
            if version == "1.1":
                _exact_arguments(arguments, f"{where}.arguments")
        if version == "1.1":
            _validate_task_authorization(case, location, guarded)
    return suite


def load_json_document(path: str | Path) -> Any:
    """Read bounded, strict JSON without accepting JavaScript numeric extensions."""
    path = Path(path)
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_FILE_BYTES + 1)
        if len(payload) > MAX_FILE_BYTES:
            raise SuiteError(f"input file exceeds {MAX_FILE_BYTES} bytes")
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_non_json_number,
        )
    except OSError as exc:
        # Filesystem exception messages can disclose private source paths.
        raise SuiteError("cannot read valid UTF-8 JSON suite: filesystem I/O failure") from exc
    except UnicodeError as exc:
        raise SuiteError("cannot read valid UTF-8 JSON suite: invalid UTF-8") from exc
    except json.JSONDecodeError as exc:
        # JSONDecodeError can include content, position or private literals.
        raise SuiteError("cannot read valid UTF-8 JSON suite: malformed JSON") from exc
    except RecursionError as exc:
        raise SuiteError("cannot read valid UTF-8 JSON suite: excessive nesting") from exc
    return value


def load_suite(path: str | Path) -> dict[str, Any]:
    return validate_suite(load_json_document(path))
