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
            raise SuiteError(f"duplicate JSON property: {key}")
        result[key] = value
    return result


def _reject_non_json_number(token: str) -> None:
    raise SuiteError(f"non-JSON numeric constant is not allowed: {token}")


def _keys(value: Any, location: str, required: set[str], optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise SuiteError(f"{location} must be a JSON object")
    actual = set(value)
    missing = required - actual
    unexpected = actual - required - (optional or set())
    if missing or unexpected:
        raise SuiteError(f"{location}: missing={sorted(missing)}, unexpected={sorted(unexpected)}")
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


def validate_suite(suite: Any) -> dict[str, Any]:
    suite = _keys(suite, "suite", {"schema_version", "policy", "cases"})
    if suite["schema_version"] != "1.0":
        raise SuiteError("unsupported schema_version (expected 1.0)")

    policy = _keys(suite["policy"], "policy", {"tools", "max_actions"})
    limit = policy["max_actions"]
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise SuiteError("policy.max_actions must be an integer from 1 to 1000")
    tools = policy["tools"]
    if not isinstance(tools, dict) or not 1 <= len(tools) <= 100:
        raise SuiteError("policy.tools must be a nonempty object (max 100)")
    for name, config in tools.items():
        if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
            raise SuiteError(f"invalid tool name: {name!r}")
        config = _keys(
            config, f"policy.tools.{name}", set(),
            {"path_args", "allowed_roots", "url_args", "allowed_hosts"},
        )
        path_args = _strings(config.get("path_args", []), f"{name}.path_args")
        roots = _strings(config.get("allowed_roots", []), f"{name}.allowed_roots")
        url_args = _strings(config.get("url_args", []), f"{name}.url_args")
        hosts = _strings(config.get("allowed_hosts", []), f"{name}.allowed_hosts")
        if bool(path_args) != bool(roots) or bool(url_args) != bool(hosts):
            raise SuiteError(f"{name}: path_args/allowed_roots and url_args/allowed_hosts must be paired")
        if any(not _IDENTIFIER.fullmatch(arg) for arg in path_args + url_args):
            raise SuiteError(f"{name}: invalid argument name")
        if set(path_args) & set(url_args):
            raise SuiteError(f"{name}: an argument cannot be a path and URL")
        if any(not _canonical_path(root) for root in roots):
            raise SuiteError(f"{name}: allowed_roots must be canonical absolute POSIX paths")
        if any(host != host.lower() or not _HOST.fullmatch(host) or ".." in host for host in hosts):
            raise SuiteError(f"{name}: allowed_hosts must be exact lower-case DNS names")

    cases = suite["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise SuiteError(f"cases must contain 1..{MAX_CASES} entries")
    ids: set[str] = set()
    total_events = 0
    for index, case in enumerate(cases):
        location = f"cases[{index}]"
        case = _keys(case, location, {"id", "expected", "trace"}, {"description"})
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
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SuiteError(f"cannot read valid UTF-8 JSON suite: {exc}") from exc
    return value


def load_suite(path: str | Path) -> dict[str, Any]:
    return validate_suite(load_json_document(path))
