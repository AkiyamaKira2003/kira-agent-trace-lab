"""Read-only imports of saved OpenAI Responses API output objects.

Only complete output function_call items are recorded. This narrow adapter
does not process streams, input items, hosted tool calls or tool outputs;
it never contacts the API or executes any function. A local array of
responses is an application-authored archive, NOT an API response envelope.
"""

from __future__ import annotations

from typing import Any

from .schema import (
    MAX_EVENTS, SuiteError, _exact_arguments, decode_json_arguments,
    validate_suite,
)


def _extract_response_calls(
    response: Any, *, seen_ids: set[str],
) -> tuple[list[dict[str, Any]], int]:
    """Validate one completed response, retaining order and rejecting duplicate calls."""
    if not isinstance(response, dict):
        raise SuiteError("Responses input must be one response JSON object")
    if response.get("status") != "completed":
        raise SuiteError("Responses input is not completed")
    output = response.get("output")
    if not isinstance(output, list) or not 1 <= len(output) <= 1000:
        raise SuiteError("Responses output must contain 1..1000 items")

    calls: list[dict[str, Any]] = []
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

    return calls, len(output)


def _as_suite(
    calls: list[dict[str, Any]], *, policy: dict[str, Any],
    case_id: str, expected: str,
) -> dict[str, Any]:
    if not calls:
        raise SuiteError("Responses output has no completed function calls")
    return validate_suite({
        "schema_version": "1.1" if "task_guarded_tools" in policy else "1.0",
        "policy": policy,
        "cases": [{"id": case_id, "expected": expected, "trace": calls}],
    })


def import_responses_output(
    response: Any, *, policy: dict[str, Any], case_id: str, expected: str,
) -> dict[str, Any]:
    """Convert the completed function calls of one local response to a suite."""
    calls, _ = _extract_response_calls(response, seen_ids=set())
    return _as_suite(calls, policy=policy, case_id=case_id, expected=expected)


def import_responses_sequence(
    responses: Any, *, policy: dict[str, Any], case_id: str, expected: str,
) -> dict[str, Any]:
    """Convert a caller-ordered local array of complete Responses objects.

    Explicit previous_response_id values, when present, must link to the
    immediately preceding saved response. Absent/null links do not prove
    causal continuity; ordering is only that asserted by the input author.
    """
    if not isinstance(responses, list) or not 1 <= len(responses) <= 50:
        raise SuiteError("Responses sequence must contain 1..50 response objects")
    seen_responses: set[str] = set()
    seen_calls: set[str] = set()
    all_calls: list[dict[str, Any]] = []
    prior_id: str | None = None
    total_output_items = 0
    for index, response in enumerate(responses):
        if not isinstance(response, dict):
            raise SuiteError(f"responses[{index}] must be a JSON object")
        response_id = response.get("id")
        if (not isinstance(response_id, str) or not 1 <= len(response_id) <= 128
                or response_id in seen_responses):
            raise SuiteError(f"responses[{index}].id must be a unique string (max 128)")
        link = response.get("previous_response_id")
        if link is not None and (index == 0 or link != prior_id):
            raise SuiteError(f"responses[{index}].previous_response_id does not match prior response")
        seen_responses.add(response_id)
        calls, items = _extract_response_calls(response, seen_ids=seen_calls)
        total_output_items += items
        if total_output_items > MAX_EVENTS:
            raise SuiteError("Responses sequence exceeds bounded output item count")
        all_calls.extend(calls)
        prior_id = response_id
    return _as_suite(all_calls, policy=policy, case_id=case_id, expected=expected)
