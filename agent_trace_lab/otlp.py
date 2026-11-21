"""Import recorded OTLP/HTTP JSON execute_tool spans without executing any action.

Subset of OpenTelemetry GenAI execute-tool semantic conventions:
https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/execute-tool.md
"""

from __future__ import annotations

import math
import re
from typing import Any

from .schema import SuiteError, decode_json_arguments, validate_suite

_OP = "gen_ai.operation.name"
_NAME = "gen_ai.tool.name"
_ARGS = "gen_ai.tool.call.arguments"
_TRACE_ID = re.compile(r"^[a-fA-F0-9]{32}$")
_SPAN_ID = re.compile(r"^[a-fA-F0-9]{16}$")
_DECIMAL_TIMESTAMP = re.compile(r"^[0-9]{1,20}$")


def _require_list(value: Any, location: str, limit: int) -> list:
    if not isinstance(value, list) or len(value) > limit:
        raise SuiteError(f"{location} must be a list of at most {limit} entries")
    return value


def _otlp_value(value: Any, location: str, depth: int = 0) -> Any:
    """Decode a limited OTLP AnyValue; fail closed on unknown representations."""
    if depth > 12 or not isinstance(value, dict) or len(value) != 1:
        raise SuiteError(f"{location}: malformed or nested OTLP AnyValue")
    kind, payload = next(iter(value.items()))
    if kind == "stringValue" and isinstance(payload, str):
        return payload
    if kind == "boolValue" and isinstance(payload, bool):
        return payload
    if kind == "intValue" and isinstance(payload, (str, int)) and not isinstance(payload, bool):
        try:
            parsed = int(payload)
        except ValueError as exc:
            raise SuiteError(f"{location}: invalid intValue") from exc
        if not -(1 << 63) <= parsed < (1 << 63):
            raise SuiteError(f"{location}: intValue outside signed 64-bit range")
        return parsed
    if kind == "doubleValue" and type(payload) in (int, float):
        # JSON decoders can represent a 350-digit number as a Python int.
        # Both math.isfinite(int) and float(int) may raise OverflowError.
        try:
            parsed = float(payload)
        except OverflowError as exc:
            raise SuiteError(f"{location}: doubleValue outside finite float range") from exc
        if not math.isfinite(parsed):
            raise SuiteError(f"{location}: doubleValue must be finite")
        return parsed
    if kind == "arrayValue" and isinstance(payload, dict):
        # ProtoJSON normally omits empty repeated fields; explicit null or an
        # invalid value still fails validation.
        items = _require_list(payload.get("values", []), f"{location}.arrayValue", 100)
        return [_otlp_value(item, f"{location}[{i}]", depth + 1) for i, item in enumerate(items)]
    if kind == "kvlistValue" and isinstance(payload, dict):
        items = _require_list(payload.get("values", []), f"{location}.kvlistValue", 100)
        result: dict[str, Any] = {}
        for index, item in enumerate(items):
            if not isinstance(item, dict) or set(item) != {"key", "value"}:
                raise SuiteError(f"{location}: malformed kvlist entry")
            key = item["key"]
            if not isinstance(key, str) or not key or key in result:
                raise SuiteError(f"{location}: invalid or duplicate key")
            # Keys are attacker-controlled trace data and can contain secrets:
            # keep them in the result, never interpolate into error locations.
            result[key] = _otlp_value(
                item["value"], f"{location}.kvlistValue[{index}]", depth + 1
            )
        return result
    raise SuiteError(f"{location}: unsupported OTLP AnyValue kind")


def _attributes(span: dict[str, Any], location: str) -> dict[str, Any]:
    attributes = _require_list(span.get("attributes", []), f"{location}.attributes", 1000)
    result: dict[str, Any] = {}
    for item in attributes:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise SuiteError(f"{location}: invalid attribute")
        key = item["key"]
        if key in (_OP, _NAME, _ARGS):
            if key in result or "value" not in item:
                raise SuiteError(f"{location}: missing/duplicate {key}")
            result[key] = _otlp_value(item["value"], f"{location}.{key}")
    return result


def import_otlp(
    export: Any, *, policy: dict[str, Any], case_id: str, expected: str
) -> dict[str, Any]:
    """Convert OTLP JSON to a single labeled evaluation suite.

    Caller supplies the expected label. The importer cannot infer ground truth.
    """
    if not isinstance(export, dict):
        raise SuiteError("OTLP export must be an object")
    resource_spans = _require_list(export.get("resourceSpans"), "resourceSpans", 100)
    collected: list[tuple[int, dict[str, Any]]] = []
    trace_ids: set[str] = set()
    span_ids: set[str] = set()
    span_total = 0
    for ri, resource in enumerate(resource_spans):
        if not isinstance(resource, dict):
            raise SuiteError(f"resourceSpans[{ri}] must be an object")
        scopes = _require_list(resource.get("scopeSpans"), f"resourceSpans[{ri}].scopeSpans", 100)
        for si, scope in enumerate(scopes):
            if not isinstance(scope, dict):
                raise SuiteError(f"scopeSpans[{si}] must be an object")
            spans = _require_list(scope.get("spans"), f"scopeSpans[{si}].spans", 10000)
            for ti, span in enumerate(spans):
                span_total += 1
                if span_total > 10000:
                    raise SuiteError("OTLP export exceeds 10000 spans")
                if not isinstance(span, dict):
                    raise SuiteError(f"spans[{ti}] must be an object")
                attrs = _attributes(span, f"spans[{ti}]")
                if attrs.get(_OP) != "execute_tool":
                    continue
                name = attrs.get(_NAME)
                if not isinstance(name, str) or not name:
                    raise SuiteError(f"spans[{ti}]: execute_tool span has no tool name")
                if _ARGS not in attrs:
                    raise SuiteError(f"spans[{ti}]: execute_tool arguments were not recorded (opt-in)")
                args = decode_json_arguments(attrs[_ARGS], f"spans[{ti}].{_ARGS}")
                trace_id = span.get("traceId")
                span_id = span.get("spanId")
                timestamp = span.get("startTimeUnixNano")
                if (
                    not isinstance(trace_id, str)
                    or not _TRACE_ID.fullmatch(trace_id)
                    or trace_id == "0" * 32
                ):
                    raise SuiteError(f"spans[{ti}]: execute_tool span requires a valid traceId")
                if (
                    not isinstance(span_id, str)
                    or not _SPAN_ID.fullmatch(span_id)
                    or span_id == "0" * 16
                ):
                    raise SuiteError(f"spans[{ti}]: execute_tool span requires a valid spanId")
                # OTLP/JSON fixed64 accepts decimal strings and JSON integers.
                # Restrict both to the actual unsigned 64-bit wire range.
                if type(timestamp) is int:
                    time_ns = timestamp
                elif isinstance(timestamp, str) and _DECIMAL_TIMESTAMP.fullmatch(timestamp):
                    time_ns = int(timestamp)
                else:
                    raise SuiteError(f"spans[{ti}]: execute_tool span requires startTimeUnixNano")
                if not 0 <= time_ns < (1 << 64):
                    raise SuiteError(f"spans[{ti}]: execute_tool span requires startTimeUnixNano")
                trace_ids.add(trace_id.lower())
                if len(trace_ids) > 1:
                    raise SuiteError("multiple traceIds found; do not combine unrelated agent runs")
                normalized_span_id = span_id.lower()
                if normalized_span_id in span_ids:
                    # Replayed/misidentified spans must not double-count tool calls.
                    raise SuiteError(f"spans[{ti}]: duplicate spanId in recorded execute_tool trace")
                span_ids.add(normalized_span_id)
                collected.append((time_ns, {"tool": name, "arguments": args}))
    if not collected:
        raise SuiteError("no execute_tool spans found; cannot infer an empty trace")
    # Ties retain exporter order. Concurrent execution cannot be fully ordered.
    trace = [event for _, event in sorted(collected, key=lambda item: item[0])]
    suite = {
        "schema_version": "1.1" if "task_guarded_tools" in policy else "1.0",
        "policy": policy,
        "cases": [{"id": case_id, "expected": expected, "trace": trace}],
    }
    return validate_suite(suite)
