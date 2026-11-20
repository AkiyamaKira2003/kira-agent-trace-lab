"""Offline import of one *recorded* AgentDojo JSON run.

Only observed assistant function calls are converted. Other messages, model
reasoning, tool outputs, the benchmark's utility/security flags and attacker
instructions cannot confer authorization. No recorded tool is executed.
"""

from __future__ import annotations

from typing import Any

from .schema import SuiteError, _exact_arguments, validate_suite


def import_agentdojo_run(
    run: Any, *, policy: dict[str, Any], case_id: str, expected: str
) -> dict[str, Any]:
    """Convert a single local AgentDojo run into one validated policy suite.

    expected must be independently chosen by the caller. The importer never
    derives it from the harness utility or security/attack-success fields.
    """
    if not isinstance(run, dict):
        raise SuiteError("AgentDojo run must be a JSON object")
    suite_name = run.get("suite_name")
    task_id = run.get("user_task_id")
    if not isinstance(suite_name, str) or not 1 <= len(suite_name) <= 80:
        raise SuiteError("AgentDojo run.suite_name must identify one suite")
    if not isinstance(task_id, str) or not 1 <= len(task_id) <= 80:
        raise SuiteError("AgentDojo run.user_task_id must identify one task")
    if "injection_task_id" in run and run["injection_task_id"] is not None:
        inject = run["injection_task_id"]
        if not isinstance(inject, str) or not 1 <= len(inject) <= 80:
            raise SuiteError("AgentDojo run.injection_task_id must be a string or null")
    if run.get("error") is not None:
        raise SuiteError("AgentDojo run has an error; cannot infer a complete observed trace")
    messages = run.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 5000:
        raise SuiteError("AgentDojo run.messages must contain 1..5000 entries")

    trace: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for message_index, message in enumerate(messages):
        location = f"messages[{message_index}]"
        if not isinstance(message, dict):
            raise SuiteError(f"{location} must be a JSON object")
        calls = message.get("tool_calls")
        if calls is None:
            continue
        if not isinstance(calls, list) or len(calls) > 1000:
            raise SuiteError(f"{location}.tool_calls must be a list (max 1000) or null")
        if message.get("role") != "assistant":
            if calls:
                raise SuiteError(f"{location}: non-assistant tool_calls cannot be imported")
            continue
        for call_index, call in enumerate(calls):
            where = f"{location}.tool_calls[{call_index}]"
            if not isinstance(call, dict) or set(call) != {"function", "args", "id"}:
                raise SuiteError(f"{where}: unsupported AgentDojo call envelope")
            tool = call["function"]
            if not isinstance(tool, str) or not tool:
                raise SuiteError(f"{where}.function must be a nonempty tool name")
            identifier = call["id"]
            if not isinstance(identifier, str) or not 1 <= len(identifier) <= 128 or identifier in seen_ids:
                raise SuiteError(f"{where}.id must be a distinct nonempty string (max 128)")
            seen_ids.add(identifier)
            args = call["args"]
            if not isinstance(args, dict):
                raise SuiteError(f"{where}.args must be a JSON object, not a string or list")
            _exact_arguments(args, f"{where}.args")
            trace.append({"tool": tool, "arguments": args})
            if len(trace) > 1000:
                raise SuiteError("AgentDojo run exceeds 1000 recorded tool calls")

    if not trace:
        raise SuiteError("no observed assistant tool calls; cannot fabricate a clean trace")
    return validate_suite({
        "schema_version": "1.1" if "task_guarded_tools" in policy else "1.0",
        "policy": policy,
        "cases": [{"id": case_id, "expected": expected, "trace": trace}],
    })
