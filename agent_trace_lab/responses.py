"""Read-only import of one saved OpenAI Responses API response object.

Only complete output function_call items are recorded. This narrow adapter
does not process streams, input items, hosted tool calls or tool outputs;
it never contacts the API or executes any function.
"""

from __future__ import annotations

from typing import Any

from .schema import (
    SuiteError, _exact_arguments, decode_json_arguments, validate_suite,
)


def import_responses_output(
    response: Any, *, policy: dict[str, Any], case_id: str, expected: str,
) -> dict[str, Any]:
    """Convert the completed function calls of one local response to a suite."""
    if not isinstance(response, dict):
        raise SuiteError("Responses input must be one response JSON object")
    if response.get("status") != "completed":
        raise SuiteError("Responses input is not completed")
    output = response.get("output")
    if not isinstance(output, list) or not 1 <= len(output) <= 1000:
        raise SuiteError("Responses output must contain 1..1000 items")

    calls: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(output):
        location = f"output[{index}]"
        if not isinstance(item, dict):
            raise SuiteError(f"{location} must be an object")
        kind = item.get("type")
        if kind in ("reasoning", "message"):
            continue
        if kind != "function_call":
            # Hosted tools, custom calls, and unknown item shapes must not
            # silently disappear and produce a misleading "clean" trace.
            raise SuiteError(f"{location}: unsupported output item type")
        if item.get("status", "completed") != "completed":
            raise SuiteError(f"{location}: function call was not completed")
        name = item.get("name")
        if not isinstance(name, str) or not 1 <= len(name) <= 80:
            raise SuiteError(f"{location}.name must be a nonempty tool name (max 80)")
        call_id = item.get("call_id")
        if (not isinstance(call_id, str) or not 1 <= len(call_id) <= 128
                or call_id in seen_ids):
            raise SuiteError(f"{location}.call_id must be a unique string (max 128)")
        seen_ids.add(call_id)
        if "arguments" not in item:
            raise SuiteError(f"{location}.arguments is missing")
        if not isinstance(item["arguments"], str):
            raise SuiteError(f"{location}.arguments must be a JSON-object string")
        arguments = decode_json_arguments(item["arguments"], f"{location}.arguments")
        _exact_arguments(arguments, f"{location}.arguments")
        calls.append({"tool": name, "arguments": arguments})

    if not calls:
        raise SuiteError("Responses output has no completed function calls")
    return validate_suite({
        "schema_version": "1.1" if "task_guarded_tools" in policy else "1.0",
        "policy": policy,
        "cases": [{"id": case_id, "expected": expected, "trace": calls}],
    })
