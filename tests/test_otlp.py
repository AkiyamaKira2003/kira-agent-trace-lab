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

    def test_human_label_is_not_inferred(self) -> None:
        suite = self._convert(expected="deny")
        result = evaluate_suite(suite)["cases"][0]
        self.assertEqual((result["actual"], result["matched"]), ("allow", False))

    def test_no_tool_spans_is_not_treated_as_clean(self) -> None:
        self.export["resourceSpans"][0]["scopeSpans"][0]["spans"] = [{"name": "unrelated"}]
        with self.assertRaisesRegex(SuiteError, "no execute_tool"):
            self._convert()

    def test_import_orders_by_start_time_not_exporter_position(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans[1], spans[2] = spans[2], spans[1]
        self.assertEqual(self._convert()["cases"][0]["trace"][0]["tool"], "files.read")

    def test_multiple_traces_are_not_combined(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans[2]["traceId"] = "20000000000000000000000000000002"
        with self.assertRaisesRegex(SuiteError, "multiple traceIds"):
            self._convert()

    def test_missing_span_ordering_is_rejected(self) -> None:
        spans = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"]
        del spans[1]["startTimeUnixNano"]
        with self.assertRaisesRegex(SuiteError, "startTimeUnixNano"):
            self._convert()

    def test_missing_opt_in_arguments_fails_closed(self) -> None:
        attributes = self.export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["attributes"]
        attributes.pop()
        with self.assertRaisesRegex(SuiteError, "not recorded"):
            self._convert()

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
