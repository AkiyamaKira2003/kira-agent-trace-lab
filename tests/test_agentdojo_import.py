"""Synthetic AgentDojo importer tests: no execution and no consent inference."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.agentdojo import import_agentdojo_run
from agent_trace_lab.engine import evaluate_suite
from agent_trace_lab.schema import SuiteError, load_json_document, load_suite


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "examples" / "agentdojo_recorded_synthetic.json"
POLICY = ROOT / "examples" / "agentdojo_policy_simulated_scope.json"


class AgentDojoImportTests(unittest.TestCase):
    def setUp(self):
        self.run_data = load_json_document(RUN)
        self.policy = load_suite(POLICY)["policy"]

    def convert(self, run=None, *, policy=None, expected="allow"):
        return import_agentdojo_run(
            self.run_data if run is None else run,
            policy=self.policy if policy is None else policy,
            case_id="synthetic_demo", expected=expected,
        )

    def test_imports_recorded_calls_in_order_without_tool_outputs(self):
        suite = self.convert()
        trace = suite["cases"][0]["trace"]
        self.assertEqual([e["tool"] for e in trace], ["get_current_day", "search_calendar_events"])
        self.assertEqual(trace[1]["arguments"], {"query": "demo event", "date": "2026-11-20"})
        self.assertNotIn("messages", suite)
        self.assertNotIn("security", suite)
        self.assertNotIn("utility", suite)
        self.assertEqual(evaluate_suite(suite)["cases"][0]["actual"], "allow")

    def test_result_flags_do_not_determine_expected(self):
        self.run_data["utility"] = False
        self.run_data["security"] = False
        suite = self.convert(expected="deny")
        self.assertEqual(suite["cases"][0]["expected"], "deny")
        self.assertEqual(evaluate_suite(suite)["cases"][0]["actual"], "allow")

    def test_simulated_scope_contrast_not_human_consent_metric(self):
        attacked = copy.deepcopy(self.run_data)
        attacked["injection_task_id"] = "injection_task_0"
        attacked["messages"][1]["tool_calls"].append(
            {"id": "example-3", "function": "send_email", "args": {"recipients": ["demo@example.org"]}}
        )
        all_tools = {"max_actions": 5, "tools": {
            "get_current_day": {}, "search_calendar_events": {}, "send_email": {},
        }}
        permissive = evaluate_suite(self.convert(attacked, policy=all_tools, expected="deny"))
        scoped = evaluate_suite(self.convert(attacked, expected="deny"))
        self.assertEqual((permissive["cases"][0]["actual"], scoped["cases"][0]["actual"]), ("allow", "deny"))
        self.assertEqual(scoped["cases"][0]["violations"][0]["code"], "TOOL_NOT_ALLOWED")
        self.assertEqual(permissive["summary"]["confusion"]["fn"], 1)
        # Both labels are declared *simulation* expectations by this test.
        # Neither is an authenticated user-grant label or population metric.

    def test_task_guarded_policy_never_infers_grants(self):
        policy = {"max_actions": 5, "tools": {"get_current_day": {}, "search_calendar_events": {}},
                  "task_guarded_tools": ["search_calendar_events"]}
        suite = self.convert(policy=policy, expected="deny")
        self.assertEqual(suite["schema_version"], "1.1")
        self.assertNotIn("task_authorization", suite["cases"][0])
        self.assertEqual(evaluate_suite(suite)["cases"][0]["violations"][0]["code"], "TASK_GRANT_REQUIRED")

    def test_wrong_message_role_with_tool_call_is_rejected(self):
        self.run_data["messages"][1]["role"] = "tool"
        with self.assertRaisesRegex(SuiteError, "non-assistant"):
            self.convert()

    def test_missing_or_non_object_args_rejected(self):
        call = self.run_data["messages"][1]["tool_calls"][0]
        for value in ([], '{"x":1}', None):
            with self.subTest(value=value):
                candidate = copy.deepcopy(self.run_data)
                candidate["messages"][1]["tool_calls"][0]["args"] = value
                with self.assertRaisesRegex(SuiteError, "JSON object"):
                    self.convert(candidate)
        del call["args"]
        with self.assertRaisesRegex(SuiteError, "envelope"):
            self.convert()

    def test_non_json_arguments_rejected_even_on_legacy_policy(self):
        self.run_data["messages"][1]["tool_calls"][0]["args"] = {"x": float("nan")}
        with self.assertRaisesRegex(SuiteError, "finite"):
            self.convert()

    def test_missing_duplicate_and_invalid_call_id_rejected(self):
        for identifier in ("", 12, "example-2"):
            with self.subTest(id=identifier):
                candidate = copy.deepcopy(self.run_data)
                candidate["messages"][1]["tool_calls"][0]["id"] = identifier
                with self.assertRaisesRegex(SuiteError, "distinct"):
                    self.convert(candidate)

    def test_unknown_envelope_field_rejected(self):
        self.run_data["messages"][1]["tool_calls"][0]["extra"] = "untrusted"
        with self.assertRaisesRegex(SuiteError, "envelope"):
            self.convert()

    def test_missing_or_empty_recorded_calls_rejected(self):
        self.run_data["messages"][1]["tool_calls"] = None
        with self.assertRaisesRegex(SuiteError, "no observed"):
            self.convert()

    def test_missing_task_identity_and_error_rejected(self):
        for key in ("suite_name", "user_task_id"):
            candidate = copy.deepcopy(self.run_data)
            del candidate[key]
            with self.subTest(key=key), self.assertRaisesRegex(SuiteError, key):
                self.convert(candidate)
        self.run_data["error"] = "tool crashed"
        with self.assertRaisesRegex(SuiteError, "has an error"):
            self.convert()

    def test_message_count_and_call_count_bounded(self):
        self.run_data["messages"] = [{"role": "assistant", "tool_calls": []}] * 5001
        with self.assertRaisesRegex(SuiteError, "5000"):
            self.convert()
        self.run_data = load_json_document(RUN)
        item = copy.deepcopy(self.run_data["messages"][1]["tool_calls"][0])
        self.run_data["messages"] = [{"role": "assistant", "tool_calls": [
            {**item, "id": f"call-{i}"} for i in range(1001)
        ]}]
        with self.assertRaisesRegex(SuiteError, "1000"):
            self.convert()

    def test_cli_import_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "converted.json"
            command = [
                sys.executable, "-m", "agent_trace_lab", "import-agentdojo",
                str(RUN), "--policy-suite", str(POLICY),
                "--case-id", "cli_synthetic", "--expected", "allow", "--output",
            ]
            success = subprocess.run([*command, str(output)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertIn("caller-provided", success.stdout)
            self.assertEqual(evaluate_suite(load_suite(output))["cases"][0]["actual"], "allow")
            overwrite = subprocess.run([*command, str(RUN)], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(overwrite.returncode, 2)


if __name__ == "__main__":
    unittest.main()
