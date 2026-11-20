"""Synthetic structural tests for recorded SWE tool-call import; no tools are run."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_trace_lab import SuiteError, evaluate_suite, load_suite
from agent_trace_lab.schema import load_json_document
from agent_trace_lab.swe import import_swe_row

ROOT = Path(__file__).resolve().parents[1]
ROW = ROOT / "examples" / "swe_recorded_row_synthetic.json"
POLICY = ROOT / "examples" / "swe_structural_policy.json"


class SweImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = load_json_document(ROW)
        self.policy = load_suite(POLICY)["policy"]

    def _convert(self, row=None, *, expected="allow", policy=None):
        return import_swe_row(
            self.row if row is None else row,
            policy=self.policy if policy is None else policy,
            case_id="demo",
            expected=expected,
        )

    def test_imports_only_observed_tool_calls_in_order(self) -> None:
        suite = self._convert()
        self.assertEqual(suite["schema_version"], "1.0")
        self.assertEqual([call["tool"] for call in suite["cases"][0]["trace"]], [
            "bash", "str_replace_editor", "submit"
        ])
        self.assertEqual(suite, self._convert())
        self.assertNotIn("resolved", suite)
        self.assertNotIn("messages", suite)
        self.assertEqual(evaluate_suite(suite)["summary"]["matched"], 1)

    def test_task_success_is_not_interpreted_as_authorization(self) -> None:
        self.row["resolved"] = 0
        self.assertEqual(self._convert(), import_swe_row(load_json_document(ROW), policy=self.policy, case_id="demo", expected="allow"))
        report = evaluate_suite(self._convert(expected="deny"))
        self.assertEqual((report["cases"][0]["actual"], report["cases"][0]["matched"]), ("allow", False))

    def test_missing_calls_does_not_fabricate_clean_trace(self) -> None:
        self.row["messages"] = [{"role": "assistant", "tool_calls": []}]
        with self.assertRaisesRegex(SuiteError, "no assistant tool calls"):
            self._convert()

    def test_missing_function_arguments_is_rejected(self) -> None:
        del self.row["messages"][2]["tool_calls"][0]["function"]["arguments"]
        with self.assertRaisesRegex(SuiteError, "missing"):
            self._convert()

    def test_invalid_json_arguments_is_rejected(self) -> None:
        self.row["messages"][2]["tool_calls"][0]["function"]["arguments"] = "{bad"
        with self.assertRaisesRegex(SuiteError, "valid JSON"):
            self._convert()

    def test_duplicate_argument_keys_are_rejected(self) -> None:
        self.row["messages"][2]["tool_calls"][0]["function"]["arguments"] = '{"command":"a","command":"b"}'
        with self.assertRaisesRegex(SuiteError, "duplicate JSON"):
            self._convert()

    def test_non_object_arguments_are_rejected(self) -> None:
        self.row["messages"][2]["tool_calls"][0]["function"]["arguments"] = '["cat","file"]'
        with self.assertRaisesRegex(SuiteError, "JSON object"):
            self._convert()

    def test_missing_tool_name_is_rejected(self) -> None:
        del self.row["messages"][2]["tool_calls"][0]["function"]["name"]
        with self.assertRaisesRegex(SuiteError, "name must be nonempty"):
            self._convert()

    def test_tool_call_on_nonassistant_is_rejected(self) -> None:
        self.row["messages"][3]["tool_calls"] = copy.deepcopy(self.row["messages"][2]["tool_calls"])
        with self.assertRaisesRegex(SuiteError, "non-assistant tool_calls"):
            self._convert()

    def test_unsupported_tool_type_is_rejected(self) -> None:
        self.row["messages"][2]["tool_calls"][0]["type"] = "other"
        with self.assertRaisesRegex(SuiteError, "unsupported tool-call"):
            self._convert()

    def test_trace_count_is_bounded(self) -> None:
        action = self.row["messages"][2]["tool_calls"][0]
        self.row["messages"] = [{"role": "assistant", "tool_calls": [copy.deepcopy(action) for _ in range(1001)]}]
        with self.assertRaisesRegex(SuiteError, "1000"):
            self._convert()

    def test_schema_11_import_never_infers_grants(self) -> None:
        policy = load_suite(ROOT / "examples" / "task_grants.json")["policy"]
        self.row["messages"][2]["tool_calls"][0]["function"]["name"] = "forward_email"
        self.row["messages"][2]["tool_calls"][0]["function"]["arguments"] = (
            '{"to":"alice@example.org","ids":["msg_1234"]}'
        )
        self.row["messages"] = self.row["messages"][:3]
        suite = self._convert(policy=policy, expected="deny")
        self.assertEqual(suite["schema_version"], "1.1")
        self.assertNotIn("task_authorization", suite["cases"][0])
        self.assertEqual(evaluate_suite(suite)["cases"][0]["violations"][0]["code"], "TASK_GRANT_REQUIRED")

    def test_cli_and_overwrite_prevention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "imported.json"
            base = [
                sys.executable, "-m", "agent_trace_lab", "import-swe", str(ROW),
                "--policy-suite", str(POLICY), "--case-id", "cli_case",
                "--expected", "allow", "--output",
            ]
            proc = subprocess.run([*base, str(output)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("caller-provided", proc.stdout)
            self.assertEqual(evaluate_suite(load_suite(output))["summary"]["matched"], 1)
            overwritten = subprocess.run([*base, str(ROW)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(overwritten.returncode, 2)


if __name__ == "__main__":
    unittest.main()
