"""Optional offline OTLP/ProtoJSON interoperability proof using official messages.

Install opentelemetry-proto into an ignored directory; this is deliberately NOT
an Agent Trace Lab runtime dependency or a required CI test. It creates only
synthetic tool-call messages and never executes the recorded tools.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.45.2"
DEFAULT_PROTO = ROOT / "artifacts" / "otlp_proto_sdk_1_45_2"


def _official_messages(package_dir: Path):
    """Require the exact optional wheel installed in the caller's ignored dir."""
    package_dir = package_dir.resolve()
    if not package_dir.is_dir() or not (
        package_dir / f"opentelemetry_proto-{VERSION}.dist-info"
    ).is_dir():
        raise RuntimeError(
            f"Install opentelemetry-proto=={VERSION} in the selected "
            "ignored --proto-dir before running this optional proof."
        )
    sys.path.insert(0, str(package_dir))
    from google.protobuf.json_format import MessageToDict
    from google.protobuf import __version__ as protobuf_version
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue, ArrayValue, KeyValue, KeyValueList
    from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span
    from opentelemetry.proto.collector.trace.v1 import trace_service_pb2

    if not Path(trace_service_pb2.__file__).resolve().is_relative_to(package_dir):
        raise RuntimeError("Generated OTLP Protobuf definitions did not load from --proto-dir")

    return (MessageToDict, protobuf_version, ExportTraceServiceRequest,
            AnyValue, ArrayValue, KeyValue, KeyValueList, ResourceSpans, ScopeSpans, Span)


def _construct_export(messages):
    (_, _, ExportTraceServiceRequest, AnyValue, ArrayValue, KeyValue,
     KeyValueList, ResourceSpans, ScopeSpans, Span) = messages
    trace_id = bytes.fromhex("11223344556677889900aabbccddeeff")
    id_first = bytes.fromhex("1000200030004000")
    id_second = bytes.fromhex("1000200030004001")
    structured = AnyValue(kvlist_value=KeyValueList(values=[
        KeyValue(key="path", value=AnyValue(string_value="/workspace/docs/readme.md")),
        KeyValue(key="metadata", value=AnyValue(kvlist_value=KeyValueList())),
        KeyValue(key="empty_items", value=AnyValue(array_value=ArrayValue())),
        KeyValue(key="count", value=AnyValue(int_value=7)),
        KeyValue(key="ratio", value=AnyValue(double_value=0.25)),
        KeyValue(key="enabled", value=AnyValue(bool_value=True)),
    ]))

    def attr(key, value):
        return KeyValue(key=key, value=value)

    first = Span(
        trace_id=trace_id, span_id=id_first, name="execute_tool files.read",
        start_time_unix_nano=1700000000000000000,
        attributes=[
            attr("gen_ai.operation.name", AnyValue(string_value="execute_tool")),
            attr("gen_ai.tool.name", AnyValue(string_value="files.read")),
            attr("gen_ai.tool.call.arguments", structured),
        ],
    )
    second = Span(
        trace_id=trace_id, span_id=id_second, name="execute_tool docs.search",
        start_time_unix_nano=1700000000000001000,
        attributes=[
            attr("gen_ai.operation.name", AnyValue(string_value="execute_tool")),
            attr("gen_ai.tool.name", AnyValue(string_value="docs.search")),
            attr("gen_ai.tool.call.arguments",
                 AnyValue(string_value='{"query":"synthetic SDK interchange"}')),
        ],
    )
    unrelated = Span(name="unrelated span")
    return ExportTraceServiceRequest(resource_spans=[
        # Deliberately out of chronological order, plus unrelated span/scope.
        ResourceSpans(scope_spans=[
            ScopeSpans(spans=[second, unrelated, first]),
            ScopeSpans(),
        ]),
        ResourceSpans(),
        ResourceSpans(scope_spans=[ScopeSpans()]),
    ])


def _otlp_hex_ids(document, export) -> None:
    """Apply ONLY the documented OTLP/JSON deviation to Protobuf JSON bytes.

    Protobuf MessageToDict emits base64 for traceId/spanId bytes. OTLP/JSON
    requires hex for these fields. All other fields stay SDK-generated.
    """
    for resource_json, resource_pb in zip(
        document["resourceSpans"], export.resource_spans, strict=True
    ):
        for scope_json, scope_pb in zip(
            resource_json.get("scopeSpans", []), resource_pb.scope_spans, strict=True
        ):
            for span_json, span_pb in zip(
                scope_json.get("spans", []), scope_pb.spans, strict=True
            ):
                if span_pb.trace_id:
                    span_json["traceId"] = span_pb.trace_id.hex()
                if span_pb.span_id:
                    span_json["spanId"] = span_pb.span_id.hex()


def verify(proto_dir: Path) -> dict:
    messages = _official_messages(proto_dir)
    # A source-only script invoked as "python scripts/..." does not add
    # the repository parent to sys.path on every Python installation.
    sys.path.insert(0, str(ROOT))
    from agent_trace_lab.otlp import import_otlp
    from agent_trace_lab.schema import SuiteError, load_suite

    message_to_dict, protobuf_version = messages[:2]
    export = _construct_export(messages)
    wire = export.SerializeToString()
    restored = messages[2].FromString(wire)
    assert restored == export, "official binary protobuf round-trip failed"
    protojson = message_to_dict(restored, preserving_proto_field_name=False)
    scopes = protojson["resourceSpans"][0]["scopeSpans"]
    assert scopes[1] == {}, "SDK unexpectedly changed empty repeated-scope encoding"
    assert protojson["resourceSpans"][1] == {}, "SDK unexpectedly changed empty resource encoding"

    original_span = scopes[0]["spans"][0]
    expected_id = base64.b64encode(export.resource_spans[0].scope_spans[0].spans[0].trace_id)
    assert original_span["traceId"] == expected_id.decode("ascii")
    policy = load_suite(ROOT / "examples" / "suite.json")["policy"]
    try:
        import_otlp(protojson, policy=policy, case_id="sdk_interop", expected="deny")
    except SuiteError as error:
        assert "traceId" in str(error), "unexpected rejection reason"
    else:
        raise AssertionError("generic base64 ProtoJSON trace IDs incorrectly accepted as OTLP/JSON")

    doc = copy.deepcopy(protojson)
    _otlp_hex_ids(doc, restored)
    canonical_json = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    result = import_otlp(doc, policy=policy, case_id="sdk_interop", expected="deny")
    case = result["cases"][0]
    assert case["expected"] == "deny", "caller-supplied label not preserved"
    assert "task_authorization" not in case, "fabricated caller authorization"
    assert case["trace"] == [
        {"tool": "files.read", "arguments": {
            "path": "/workspace/docs/readme.md", "metadata": {}, "empty_items": [],
            "count": 7, "ratio": 0.25, "enabled": True,
        }},
        {"tool": "docs.search", "arguments": {"query": "synthetic SDK interchange"}},
    ], "SDK-generated tool calls were not faithfully imported and ordered"

    task_policy = load_suite(ROOT / "examples" / "task_grants.json")["policy"]
    guarded = import_otlp(doc, policy=task_policy, case_id="guarded", expected="deny")
    assert guarded["schema_version"] == "1.1"
    assert "task_authorization" not in guarded["cases"][0]

    no_tools = copy.deepcopy(doc)
    no_tools["resourceSpans"][0]["scopeSpans"][0]["spans"] = [
        {"name": "unrelated"}
    ]
    try:
        import_otlp(no_tools, policy=policy, case_id="empty", expected="allow")
    except SuiteError as error:
        assert "no execute_tool" in str(error)
    else:
        raise AssertionError("missing execute_tool was inferred as a clean empty trace")

    with tempfile.TemporaryDirectory(prefix="atl-004dh-") as tmp:
        scratch = Path(tmp)
        source = scratch / "synthetic_official_otlp.json"
        positive = scratch / "converted.json"
        source.write_text(json.dumps(doc), encoding="utf-8")

        def cli(output: Path) -> subprocess.CompletedProcess[str]:
            return subprocess.run([
                sys.executable, "-m", "agent_trace_lab", "import-otlp",
                str(source), "--policy-suite", str(ROOT / "examples" / "suite.json"),
                "--case-id", "sdk_cli", "--expected", "deny", "--output", str(output),
            ], cwd=ROOT, capture_output=True, text=True, timeout=15)

        good = cli(positive)
        assert good.returncode == 0, f"positive CLI import failed: {good.stderr}"
        actual = json.loads(positive.read_text(encoding="utf-8"))
        assert actual["cases"][0]["trace"] == case["trace"]
        assert actual["cases"][0]["expected"] == "deny"

        marker = "SYNTHETIC_PRIVATE_004DH_DO_NOT_ECHO"
        corrupted = copy.deepcopy(doc)
        broken = corrupted["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        broken["traceId"] = "not-hex"
        broken["attributes"][2]["value"] = {
            "stringValue": json.dumps({"private": marker}),
        }
        source.write_text(json.dumps(corrupted), encoding="utf-8")
        negative = scratch / "must-not-appear.json"
        failed = cli(negative)
        assert failed.returncode == 2, f"negative CLI did not fail closed: {failed.returncode}"
        assert marker not in failed.stdout + failed.stderr, "synthetic marker echoed"
        assert "Traceback" not in failed.stderr
        assert not negative.exists(), "invalid import wrote an output file"

    return {
        "official_proto_version": VERSION,
        "protobuf_runtime_version": protobuf_version,
        "synthetic_proto_wire_sha256": hashlib.sha256(wire).hexdigest(),
        "normalized_otlp_json_sha256": hashlib.sha256(canonical_json.encode("utf-8")).hexdigest(),
        "generic_protobuf_json_ids": "base64, rejected",
        "otlp_json_hex_ids": "accepted",
        "sdk_generated_tool_calls": len(case["trace"]),
        "empty_resource_and_scope": "accepted",
        "nested_anyvalue": "accepted without fabricated data",
        "guarded_task_authorization": "absent as required",
        "cli_positive": "pass",
        "cli_negative": "exit 2, no file/marker/traceback",
    }


def main() -> None:
    if not __debug__:
        raise RuntimeError("The verification script relies on assertions; do not use Python -O.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proto-dir", type=Path, default=DEFAULT_PROTO,
                        help="directory containing pinned optional opentelemetry-proto wheel")
    args = parser.parse_args()
    print(json.dumps(verify(args.proto_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
