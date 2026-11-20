"""Read-only import of a *single* recorded SWE-agent-style JSON row.

This extracts observed assistant tool calls, not tool outputs or user intent.
It neither executes calls nor interprets whether the issue was resolved.
"""

from __future__ import annotations

from typing import Any

from .schema import SuiteError, decode_json_arguments, validate_suite


def import_swe_row(
    row: Any, *, policy: dict[str, Any], case_id: str, expected: str
) -> dict[str, Any]:
    """Produce one validated suite from locally supplied benchmark-row data."""
    if not isinstance(row, dict):
        raise SuiteError("SWE row must be a JSON object")
    messages = row.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 5000:
        raise SuiteError("SWE row.messages must contain 1..5000 entries")
    trace: list[dict[str, Any]] = []
    for message_index, message in enumerate(messages):
        where = f"messages[{message_index}]"
        if not isinstance(message, dict):
            raise SuiteError(f"{where} must be an object")
        role = message.get("role")
        calls = message.get("tool_calls")
        if calls is None:
            continue
        if not isinstance(calls, list) or len(calls) > 1000:
            raise SuiteError(f"{where}.tool_calls must be a list (max 1000) or null")
        if role != "assistant":
            if calls:
                raise SuiteError(f"{where}: non-assistant tool_calls cannot be imported")
            continue
        for call_index, call in enumerate(calls):
            location = f"{where}.tool_calls[{call_index}]"
            if not isinstance(call, dict) or call.get("type", "function") != "function":
                raise SuiteError(f"{location}: unsupported tool-call envelope")
            function = call.get("function")
            if not isinstance(function, dict):
                raise SuiteError(f"{location}.function must be an object")
            tool = function.get("name")
            if not isinstance(tool, str) or not tool:
                raise SuiteError(f"{location}.function.name must be nonempty")
            if "arguments" not in function:
                raise SuiteError(f"{location}: recorded function.arguments is missing")
            arguments = decode_json_arguments(function["arguments"], f"{location}.function.arguments")
            trace.append({"tool": tool, "arguments": arguments})
            if len(trace) > 1000:
                raise SuiteError("SWE row has more than 1000 tool calls")
    if not trace:
        raise SuiteError("no assistant tool calls found; cannot infer a clean trace")
    suite = {
        "schema_version": "1.1" if "task_guarded_tools" in policy else "1.0",
        "policy": policy,
        "cases": [{"id": case_id, "expected": expected, "trace": trace}],
    }
    return validate_suite(suite)
