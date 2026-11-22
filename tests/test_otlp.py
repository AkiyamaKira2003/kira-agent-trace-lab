from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_trace_lab import SuiteError, evaluate_suite, load_suite
from agent_trace_lab.otlp import _otlp_value, import_otlp
from agent_trace_lab.schema import load_json_document

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "examples" / "suite.json"
TRACE = ROOT / "examples" / "otlp_spans.json"


class OtlpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.export = load_json_document(TRACE)
        self.policy = load_suite(POLICY)["policy"]

    def _convert(self, export=None, *, expected="allow"):
        return import_otlp(
            self.export if export is None else export,
            policy=self.policy,
            case_id="recorded_1",
            expected=expected,
        )

    def test_import_preserves_order_and_is_reproducible(self) -> None:
        suite = self._convert()
        self.assertEqual([x["tool"] for x in suite["cases"][0]["trace"]], ["files.read", "docs.search"])
        self.assertEqual(suite, self._convert())
        self.assertEqual(evaluate_suite(suite)["summary"]["matched"], 1)

    def test_explicit_two_export_envelopes_require_external_completion_contract(self) -> None:
        """One valid HTTP export cannot prove that a trace has no later batches."""
        first = copy.deepcopy(self.export)
        second = copy.deepcopy(self.export)
        first["resourceSpans"][0]["scopeSpans"][0]["spans"] = (
            first["resourceSpans"][0]["scopeSpans"][0]["spans"][:2]
        )
        second["resourceSpans"][0]["scopeSpans"][0]["spans"] = (
            second["resourceSpans"][0]["scopeSpans"][0]["spans"][2:]
        )
        self.assertEqual([e["tool"] for e in self._convert(first)["cases"][0]["trace"]], ["files.read"])
        self.assertEqual([e["tool"] for e in self._convert(second)["cases"][0]["trace"]], ["docs.search"])
        with self.assertRaisesRegex(SuiteError, "OTLP export must be an object"):
            self._convert([first, second])
        # This is a caller-assembled fixture, not evidence that all network
        # batches were received. Only a complete external capture may combine.
        complete = {"resourceSpans": first["resourceSpans"] + second["resourceSpans"]}
        self.assertEqual(
            [e["tool"] for e in self._convert(complete)["cases"][0]["trace"]],
            ["files.read", "docs.search"],
        )
        duplicate = copy.deepcopy(complete)
        duplicate["resourceSpans"][1]["scopeSpans"][0]["spans"][0]["spanId"] = (
            duplicate["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["spanId"]
        )
        with self.assertRaisesRegex(SuiteError, "duplicate spanId"):
            self._convert(duplicate)
        wrong_run = copy.deepcopy(complete)
        wrong_run["resourceSpans"][1]["scopeSpans"][0]["spans"][0]["traceId"] = "a" * 32
        with self.assertRaisesRegex(SuiteError, "multiple traceIds"):
            self._convert(wrong_run)

    def test_human_label_is_not_inferred(self) -> None:
        suite = self._convert(expected="deny")
        result = evaluate_suite(suite)["cases"][0]
        self.assertEqual((result["actual"], result["matched"]), ("allow", False))

    def test_no_tool_spans_is_not_treated_as_clean(self) -> None:
        self.export["resourceSpans"][0]["scopeSpans"][0]["spans"] = [{"name": "unrelated"}]
        with self.assertRaisesRegex(SuiteError, "no execute_tool"):
            self._convert()

    def test_protojson_omitted_empty_span_groups_do_not_block_recorded_tools(self) -> None:
        # OTLP trace.proto defines both lists as repeated fields; ProtoJSON
        # may omit them when empty in unrelated resource/scope groups.
        baseline = self._convert()
        self.export["resourceSpans"].extend([
            {"resource": {"attributes": []}},
            {"scopeSpans": [{"scope": {"name": "unused"}}]},
        ])
        self.assertEqual(self._convert(), baseline)

    def test_protojson_omitted_empty_span_groups_are_not_inferred_as_tool_calls(self) -> None:
        for export in (
            {"resourceSpans": [{}]},
            {"resourceSpans": [{"scopeSpans": [{}]}]},
        ):
            with self.subTest(export=export):
                with self.assertRaisesRegex(SuiteError, "no execute_tool"):
                    self._convert(export)

    def test_malformed_span_group_lists_are_rejected_not_silently_skipped(self) -> None:
        for payload in (None, {}, "not a list", [None]):
            with self.subTest(payload=payload):
                with self.assertRaises(SuiteError):
                    self._convert({"resourceSpans": [{"scopeSpans": payload}]})
                with self.assertRaises(SuiteError):
                    self._convert({"resourceSpans": [{"scopeSpans": [{"spans": payload}]}]})

    def test_import_orders_by_start_time_not_exporter_position(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans[1], spans[2] = spans[2], spans[1]
        self.assertEqual(self._convert()["cases"][0]["trace"][0]["tool"], "files.read")

    def test_multiple_traces_are_not_combined(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans[2]["traceId"] = "20000000000000000000000000000002"
        with self.assertRaisesRegex(SuiteError, "multiple traceIds"):
            self._convert()

    def test_duplicate_span_identity_is_not_a_second_tool_call(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans.append(copy.deepcopy(spans[1]))
        with self.assertRaisesRegex(SuiteError, "duplicate spanId"):
            self._convert()

    def test_duplicate_span_id_is_rejected_across_scope_boundaries_and_hex_case(self) -> None:
        resource = self.export["resourceSpans"][0]
        span = copy.deepcopy(resource["scopeSpans"][0]["spans"][1])
        span["spanId"] = span["spanId"].upper()
        resource["scopeSpans"].append({"spans": [span]})
        with self.assertRaisesRegex(SuiteError, "duplicate spanId"):
            self._convert()

    def test_execute_tool_requires_nonzero_span_and_trace_ids(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        for invalid in (None, "", "0" * 16, "g" * 16, "a" * 15):
            with self.subTest(spanId=invalid):
                changed = copy.deepcopy(self.export)
                target = changed["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
                if invalid is None:
                    target.pop("spanId")
                else:
                    target["spanId"] = invalid
                with self.assertRaisesRegex(SuiteError, "spanId"):
                    self._convert(changed)
        for invalid in ("0" * 32, "0" * 31, "z" * 32):
            with self.subTest(traceId=invalid):
                changed = copy.deepcopy(self.export)
                target = changed["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
                target["traceId"] = invalid
                with self.assertRaisesRegex(SuiteError, "traceId"):
                    self._convert(changed)

    def test_span_id_hex_casing_does_not_change_valid_tool_trace(self) -> None:
        before = self._convert()
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans[1]["spanId"] = "ABCDEF1234567890"
        spans[2]["spanId"] = "ABCDEF1234567891"
        self.assertEqual(self._convert()["cases"][0]["trace"], before["cases"][0]["trace"])

    def test_cli_replayed_span_is_rejected_without_leaking_identifiers(self) -> None:
        marker = "SYNTHETIC_PRIVATE_TRACE_ARG_876"
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        duplicate = copy.deepcopy(spans[1])
        duplicate["attributes"][2]["value"] = {
            "stringValue": json.dumps({"path": marker}),
        }
        spans.append(duplicate)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "duplicated.json"
            dest = Path(tmp) / "not_written.json"
            source.write_text(json.dumps(self.export), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, "-m", "agent_trace_lab", "import-otlp",
                    str(source), "--policy-suite", str(POLICY),
                    "--case-id", "duplicate", "--expected", "allow",
                    "--output", str(dest),
                ],
                cwd=ROOT, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("duplicate spanId", proc.stderr)
            self.assertNotIn(marker, proc.stderr + proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse(dest.exists())

    def test_missing_span_ordering_is_rejected(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        del spans[1]["startTimeUnixNano"]
        with self.assertRaisesRegex(SuiteError, "startTimeUnixNano"):
            self._convert()

    def test_timestamp_accepts_otlp_fixed64_json_number_and_boundaries(self) -> None:
        baseline = self._convert()
        for timestamp in (1795146000000000000, 0, (1 << 64) - 1):
            with self.subTest(timestamp=timestamp):
                changed = copy.deepcopy(self.export)
                changed["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["startTimeUnixNano"] = timestamp
                self.assertEqual(len(self._convert(changed)["cases"][0]["trace"]), 2)
        numeric = copy.deepcopy(self.export)
        for span in numeric["resourceSpans"][0]["scopeSpans"][0]["spans"][1:]:
            span["startTimeUnixNano"] = int(span["startTimeUnixNano"])
        self.assertEqual(self._convert(numeric), baseline)

    def test_timestamp_rejects_out_of_uint64_and_non_ascii_digits(self) -> None:
        bad_timestamps = (
            str(1 << 64), 1 << 64, -1, "-1", True, 1.25,
            "١٧٩٥١٤٦٠٠٠٠٠٠٠٠٠٠٠", "0" * 21, "1.0",
        )
        for timestamp in bad_timestamps:
            with self.subTest(kind=type(timestamp).__name__):
                changed = copy.deepcopy(self.export)
                changed["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["startTimeUnixNano"] = timestamp
                with self.assertRaisesRegex(SuiteError, "startTimeUnixNano"):
                    self._convert(changed)

    def test_cli_invalid_timestamp_fails_closed_without_leaking(self) -> None:
        marker = "SYNTHETIC_PRIVATE_TIMESTAMP_ARG"
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans[1]["startTimeUnixNano"] = str(1 << 64)
        spans[1]["attributes"][2]["value"] = {
            "stringValue": json.dumps({"path": marker}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "overflow_timestamp.json"
            dest = Path(tmp) / "converted.json"
            source.write_text(json.dumps(self.export), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, "-m", "agent_trace_lab", "import-otlp",
                    str(source), "--policy-suite", str(POLICY),
                    "--case-id", "overflow", "--expected", "allow",
                    "--output", str(dest),
                ],
                cwd=ROOT, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("startTimeUnixNano", proc.stderr)
            self.assertNotIn(marker, proc.stdout + proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse(dest.exists())

    def test_cli_otlp_fixed64_numeric_json_timestamp_is_supported(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        for span in spans[1:]:
            span["startTimeUnixNano"] = int(span["startTimeUnixNano"])
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "number_timestamps.json"
            dest = Path(tmp) / "number_converted.json"
            source.write_text(json.dumps(self.export), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, "-m", "agent_trace_lab", "import-otlp",
                    str(source), "--policy-suite", str(POLICY),
                    "--case-id", "numeric_start", "--expected", "allow",
                    "--output", str(dest),
                ],
                cwd=ROOT, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(load_suite(dest)["cases"][0]["trace"]), 2)

    def test_missing_opt_in_arguments_fails_closed(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes.pop()
        with self.assertRaisesRegex(SuiteError, "not recorded"):
            self._convert()

    def test_execute_tool_accepts_protojson_empty_kvlist_for_no_arguments(self) -> None:
        # ProtoJSON omits empty repeated fields by default; the corresponding
        # OTLP KeyValueList is {"kvlistValue": {}} rather than values=[].
        span = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
        span["attributes"][2]["value"] = {"kvlistValue": {}}
        suite = self._convert()
        self.assertEqual(suite["cases"][0]["trace"][0], {
            "tool": "files.read", "arguments": {},
        })

    def test_nested_omitted_repeated_anyvalue_fields_are_empty_not_null(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes[2]["value"] = {"kvlistValue": {"values": [
            {"key": "items", "value": {"arrayValue": {}}},
            {"key": "metadata", "value": {"kvlistValue": {}}},
        ]}}
        suite = self._convert()
        self.assertEqual(suite["cases"][0]["trace"][0]["arguments"], {
            "items": [], "metadata": {},
        })
        for kind in ("arrayValue", "kvlistValue"):
            with self.subTest(kind=kind):
                with self.assertRaises(SuiteError):
                    _otlp_value({kind: {"values": None}}, "safe")
                for malformed in ({"unexpected": []}, {"values": [], "unexpected": []}):
                    with self.assertRaises(SuiteError):
                        _otlp_value({kind: malformed}, "safe")

    def test_malformed_json_arguments_fails_closed(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes[2]["value"]["stringValue"] = "{invalid"
        with self.assertRaisesRegex(SuiteError, "valid JSON"):
            self._convert()

    def test_duplicate_instrumentation_attributes_rejected(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes.append(copy.deepcopy(attributes[1]))
        with self.assertRaisesRegex(SuiteError, "duplicate"):
            self._convert()

    def test_duplicate_json_argument_keys_rejected(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes[2]["value"]["stringValue"] = '{"path":"/workspace/docs/a","path":"/workspace/docs/b"}'
        with self.assertRaisesRegex(SuiteError, "duplicate"):
            self._convert()

    def test_unsupported_otel_anyvalue_rejected(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes[2]["value"] = {"bytesValue": "Zm9v"}
        with self.assertRaisesRegex(SuiteError, "unsupported"):
            self._convert()

    def test_nested_kvlist_errors_do_not_echo_untrusted_property_names(self) -> None:
        marker = "SYNTHETIC_PRIVATE_KEY_DO_NOT_LOG_123"
        for bad_value in ({"bytesValue": "Zm9v"}, {"intValue": "invalid_integer"}):
            with self.subTest(kind=next(iter(bad_value))):
                value = {"kvlistValue": {"values": [
                    {"key": marker, "value": bad_value},
                ]}}
                with self.assertRaises(SuiteError) as caught:
                    _otlp_value(value, "spans[0].gen_ai.tool.call.arguments")
                self.assertIn("kvlistValue[0]", str(caught.exception))
                self.assertNotIn(marker, str(caught.exception))

    def test_nested_kvlist_keeps_original_argument_keys_on_valid_input(self) -> None:
        marker = "SYNTHETIC_PRIVATE_KEY_DO_NOT_LOG_123"
        value = {"kvlistValue": {"values": [
            {"key": marker, "value": {"stringValue": "synthetic_value"}},
        ]}}
        self.assertEqual(_otlp_value(value, "example"), {marker: "synthetic_value"})

    def test_otlp_int64_limits_reject_out_of_range_values(self) -> None:
        for payload in (str(1 << 63), -(1 << 63) - 1, 1 << 350):
            with self.subTest(out_of_range=True):
                with self.assertRaisesRegex(SuiteError, "signed 64-bit range"):
                    _otlp_value({"intValue": payload}, "safe.OTLP.location")
        for number in (-(1 << 63), (1 << 63) - 1, 0):
            with self.subTest(value=number):
                self.assertEqual(_otlp_value({"intValue": str(number)}, "safe"), number)

    def test_otlp_giant_double_is_safe_validation_error_not_overflow(self) -> None:
        for payload in (10 ** 350, -(10 ** 350), float("inf"), float("nan")):
            with self.subTest(kind=type(payload).__name__):
                with self.assertRaises(SuiteError) as caught:
                    _otlp_value({"doubleValue": payload}, "safe.OTLP.location")
                self.assertIn("doubleValue", str(caught.exception))
        self.assertEqual(_otlp_value({"doubleValue": 3.25}, "safe"), 3.25)
        self.assertEqual(_otlp_value({"doubleValue": 123}, "safe"), 123.0)

    def test_cli_oversized_otlp_numeric_arguments_fail_without_traceback(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        for kind, payload in (("doubleValue", 10 ** 350), ("intValue", str(1 << 64))):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                original = copy.deepcopy(attributes[2]["value"])
                try:
                    attributes[2]["value"] = {"kvlistValue": {"values": [
                        {"key": "test_numeric", "value": {kind: payload}},
                    ]}}
                    source = Path(tmp) / "synthetic_numeric_otlp.json"
                    dest = Path(tmp) / "converted.json"
                    source.write_text(json.dumps(self.export), encoding="utf-8")
                    result = subprocess.run(
                        [
                            sys.executable, "-m", "agent_trace_lab",
                            "import-otlp", str(source),
                            "--policy-suite", str(POLICY), "--case-id", "numeric_bounds",
                            "--expected", "allow", "--output", str(dest),
                        ],
                        cwd=ROOT, capture_output=True, text=True, timeout=15,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn(kind, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertFalse(dest.exists())
                finally:
                    attributes[2]["value"] = original

    def test_cli_otlp_invalid_nested_key_is_not_logged(self) -> None:
        marker = "SYNTHETIC_PRIVATE_KEY_DO_NOT_LOG_123"
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes[2]["value"] = {"kvlistValue": {"values": [
            {"key": marker, "value": {"bytesValue": "Zm9v"}},
        ]}}
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "bad_otlp.json"
            raw.write_text(json.dumps(self.export), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, "-m", "agent_trace_lab", "import-otlp", str(raw),
                    "--policy-suite", str(POLICY), "--case-id", "demo",
                    "--expected", "allow", "--output", str(Path(tmp) / "converted.json"),
                ],
                cwd=ROOT, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("kvlistValue[0]", result.stderr)
            self.assertNotIn(marker, result.stderr + result.stdout)

    def test_invalid_trace_path_in_integrated_report(self) -> None:
        attrs = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attrs[2]["value"]["stringValue"] = '{"path":"/workspace/docs/../private"}'
        report = evaluate_suite(self._convert())
        self.assertEqual(report["cases"][0]["actual"], "deny")
        self.assertEqual(report["cases"][0]["violations"][0]["code"], "PATH_INVALID")

    def test_cli_import_uses_explicit_label_and_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "imported.json"
            cmd = [
                sys.executable, "-m", "agent_trace_lab", "import-otlp", str(TRACE),
                "--policy-suite", str(POLICY), "--case-id", "ci_case",
                "--expected", "allow", "--output", str(output),
            ]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("user-provided", proc.stdout)
            self.assertEqual(evaluate_suite(load_suite(output))["summary"]["matched"], 1)
            overwrite = cmd.copy()
            overwrite[-1] = str(TRACE)
            bad = subprocess.run(overwrite, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)

    def test_import_with_task_guards_has_no_assumed_grants(self) -> None:
        policy = load_suite(ROOT / "examples" / "task_grants.json")["policy"]
        export = copy.deepcopy(self.export)
        export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"][1]["value"]["stringValue"] = "forward_email"
        export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"][2]["value"]["stringValue"] = (
            '{"to":"alice@example.org","ids":["msg_1234"]}'
        )
        suite = import_otlp(export, policy=policy, case_id="no_user_grant", expected="deny")
        self.assertEqual(suite["schema_version"], "1.1")
        self.assertNotIn("task_authorization", suite["cases"][0])
        report = evaluate_suite(suite)
        self.assertEqual(report["cases"][0]["actual"], "deny")
        self.assertEqual(report["cases"][0]["violations"][0]["code"], "TASK_GRANT_REQUIRED")


if __name__ == "__main__":
    unittest.main()
