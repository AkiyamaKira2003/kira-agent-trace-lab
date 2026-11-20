"""Regression cases for the opt-in task-authorization protocol."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_trace_lab import SuiteError, evaluate_suite, load_suite, validate_suite

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "task_grants.json"


class TaskGrantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = load_suite(FIXTURE)

    def test_allow_and_deny_examples(self) -> None:
        result = evaluate_suite(self.suite)
        self.assertEqual(result["schema_version"], "1.1")
        self.assertEqual(result["summary"]["matched"], 9)
        self.assertEqual(result["summary"]["confusion"], {"tp": 5, "tn": 4, "fp": 0, "fn": 0})
        self.assertEqual([case["actual"] for case in result["cases"]], [
            "allow", "deny", "deny", "deny", "deny", "allow", "allow", "allow", "deny"
        ])

    def test_replay_requires_two_grants(self) -> None:
        results = evaluate_suite(self.suite)["cases"]
        self.assertEqual(results[4]["violations"], [{
            "event_index": 1, "tool": "forward_email", "code": "TASK_GRANT_REQUIRED",
        }])
        self.assertEqual(results[5]["violations"], [])

    def test_no_grant_does_not_allow_guarded_action(self) -> None:
        self.assertEqual(evaluate_suite(self.suite)["cases"][2]["violations"][0]["code"], "TASK_GRANT_REQUIRED")

    def test_altering_resource_or_argument_type_denies(self) -> None:
        case = self.suite["cases"][0]
        case["trace"][0]["arguments"]["ids"] = ["msg_1234", "msg_5678"]
        self.assertEqual(evaluate_suite(self.suite)["cases"][0]["actual"], "deny")
        case["trace"][0]["arguments"]["ids"] = "msg_1234"
        self.assertEqual(evaluate_suite(self.suite)["cases"][0]["actual"], "deny")

    def test_grants_cannot_override_tool_rules(self) -> None:
        self.suite["policy"]["tools"]["forward_email"] = {
            "url_args": ["url"], "allowed_hosts": ["internal.example.org"]
        }
        violations = evaluate_suite(self.suite)["cases"][0]["violations"]
        self.assertIn("MISSING_ARGUMENT", [v["code"] for v in violations])

    def test_grant_does_not_trust_source_ref_itself(self) -> None:
        # Matching data is not authenticated consent; the engine never contacts source_ref.
        grant = self.suite["cases"][0]["task_authorization"]["grants"][0]
        grant["source_ref"] = "unverified:claimed-by-agent"
        self.assertEqual(evaluate_suite(self.suite)["cases"][0]["actual"], "allow")

    def test_duplicate_grant_id_rejected(self) -> None:
        case = self.suite["cases"][0]
        duplicate = copy.deepcopy(case["task_authorization"]["grants"][0])
        case["task_authorization"]["grants"].append(duplicate)
        with self.assertRaisesRegex(SuiteError, "distinct identifier"):
            validate_suite(self.suite)

    def test_grant_for_unguarded_tool_rejected(self) -> None:
        self.suite["cases"][0]["task_authorization"]["grants"][0]["tool"] = "search_inbox"
        with self.assertRaisesRegex(SuiteError, "guarded tools"):
            validate_suite(self.suite)

    def test_grant_with_invalid_source_ref_rejected(self) -> None:
        self.suite["cases"][0]["task_authorization"]["grants"][0]["source_ref"] = " \n"
        with self.assertRaisesRegex(SuiteError, "printable"):
            validate_suite(self.suite)

    def test_missing_grants_object_is_explicitly_denied(self) -> None:
        self.suite["cases"][0]["task_authorization"]["grants"] = []
        self.assertEqual(evaluate_suite(self.suite)["cases"][0]["actual"], "deny")

    def test_ambiguous_null_authorization_is_rejected(self) -> None:
        self.suite["cases"][0]["task_authorization"] = None
        with self.assertRaisesRegex(SuiteError, "must be an object"):
            validate_suite(self.suite)

    def test_argument_values_are_strictly_typed(self) -> None:
        case = self.suite["cases"][0]
        case["trace"][0]["arguments"]["ids"] = ["msg_1234"]
        case["trace"][0]["arguments"]["to"] = "alice@example.org"
        case["task_authorization"]["grants"][0]["arguments"]["to"] = True
        self.assertEqual(evaluate_suite(self.suite)["cases"][0]["actual"], "deny")

    def test_unsupported_float_constant_rejected_in_new_schema(self) -> None:
        case = self.suite["cases"][0]
        case["trace"][0]["arguments"]["untrusted"] = float("nan")
        with self.assertRaisesRegex(SuiteError, "finite"):
            validate_suite(self.suite)

    def test_invalid_nested_grant_values_rejected(self) -> None:
        self.suite["cases"][0]["task_authorization"]["grants"][0]["arguments"]["ids"] = {1, 2}
        with self.assertRaisesRegex(SuiteError, "unsupported JSON"):
            validate_suite(self.suite)

    def test_non_string_nested_json_keys_rejected(self) -> None:
        self.suite["cases"][0]["task_authorization"]["grants"][0]["arguments"]["nested"] = {1: "x"}
        with self.assertRaisesRegex(SuiteError, "invalid JSON object keys"):
            validate_suite(self.suite)

    def test_legacy_version_refuses_new_fields(self) -> None:
        legacy = load_suite(ROOT / "examples" / "suite.json")
        legacy["policy"]["task_guarded_tools"] = ["docs.search"]
        with self.assertRaises(SuiteError):
            validate_suite(legacy)
        self.assertEqual(evaluate_suite(load_suite(ROOT / "examples" / "suite.json"))["summary"]["matched"], 8)

    def test_task_guarded_tools_must_be_allowed(self) -> None:
        self.suite["policy"]["task_guarded_tools"] = ["shell.run"]
        with self.assertRaisesRegex(SuiteError, "allowlisted"):
            validate_suite(self.suite)

    def test_cli_works_for_new_version(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "agent_trace_lab", "evaluate", str(FIXTURE), "--format", "json"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["summary"]["matched"], 9)


if __name__ == "__main__":
    unittest.main()
