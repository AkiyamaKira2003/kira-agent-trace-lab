"""Acceptance and negative tests for the self-authored end-user CLI contrast."""

from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from agent_trace_lab.engine import evaluate_suite
from agent_trace_lab.schema import SuiteError, load_suite
from scripts.verify_installed_wheel import _execute, validate_policy_contrast

ROOT = Path(__file__).resolve().parents[1]
BROAD_PATH = ROOT / "examples" / "demo_permissive.json"
SCOPED_PATH = ROOT / "examples" / "demo_task_scoped.json"


class PolicyContrastDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.broad_suite = load_suite(BROAD_PATH)
        self.scoped_suite = load_suite(SCOPED_PATH)
        self.broad = evaluate_suite(self.broad_suite)
        self.scoped = evaluate_suite(self.scoped_suite)

    def test_exact_demo_verdicts_match_supported_engine_behavior(self):
        validate_policy_contrast(self.broad, self.scoped)
        self.assertEqual(self.broad["summary"]["matched"], 0)
        self.assertEqual(self.scoped["summary"]["matched"], 5)
        self.assertEqual(self.scoped["summary"]["confusion"], {
            "tp": 3, "tn": 2, "fp": 0, "fn": 0,
        })

    def test_same_unrequested_action_has_different_verdict_under_explicit_policy(self):
        a = self.broad_suite["cases"][0]["trace"]
        b = self.scoped_suite["cases"][0]["trace"]
        self.assertEqual(a, b)
        self.assertEqual(self.broad["cases"][0]["actual"], "allow")
        self.assertEqual(self.scoped["cases"][0]["actual"], "deny")
        self.assertEqual(self.scoped["cases"][0]["violations"][0]["code"],
                         "TASK_GRANT_REQUIRED")

    def test_grants_are_obviously_fictional_not_issuer_authenticated(self):
        self.assertEqual(self.scoped_suite["schema_version"], "1.1")
        self.assertEqual(self.scoped_suite["policy"]["task_guarded_tools"], ["forward_email"])
        self.assertNotIn("task_authorization", self.scoped_suite["cases"][0])
        for case in self.scoped_suite["cases"]:
            for event in case["trace"]:
                self.assertEqual(event["tool"] in ("forward_email", "search_inbox"), True)
                for value in event["arguments"].values():
                    if isinstance(value, str) and "@" in value:
                        self.assertTrue(value.endswith("@example.invalid"))
            for grant in case.get("task_authorization", {}).get("grants", []):
                self.assertEqual(grant["source_ref"], "self-authored-fictional-demo-only")

    def test_guard_cannot_consume_one_grant_twice(self):
        replayed = self.scoped["cases"][3]["violations"]
        self.assertEqual(len(replayed), 1)
        self.assertEqual(replayed[0]["event_index"], 1)
        self.assertEqual(replayed[0]["tool"], "forward_email")

    def test_demo_verifier_rejects_fabricated_success_or_denial_reason(self):
        variants = [
            ("permissive_made_to_match", "broad", 0, "matched", True),
            ("permissive_denied", "broad", 0, "actual", "deny"),
            ("scoped_accepts_unrequested", "scoped", 0, "actual", "allow"),
            ("scoped_approves_redirect", "scoped", 2, "actual", "allow"),
            ("scoped_approves_replay", "scoped", 3, "actual", "allow"),
            ("scoped_bad_reason", "scoped", 2, "violations",
             [{"event_index": 0, "tool": "forward_email", "code": "TOOL_NOT_ALLOWED"}]),
        ]
        for name, side, index, field, value in variants:
            with self.subTest(name=name):
                broad, scoped = copy.deepcopy(self.broad), copy.deepcopy(self.scoped)
                chosen = broad if side == "broad" else scoped
                chosen["cases"][index][field] = value
                with self.assertRaises(SuiteError):
                    validate_policy_contrast(broad, scoped)

    def test_demo_verifier_rejects_missing_or_injected_result_cases(self):
        for name in ("missing", "injected", "reordered"):
            with self.subTest(name=name):
                scoped = copy.deepcopy(self.scoped)
                if name == "missing":
                    scoped["cases"].pop()
                elif name == "injected":
                    scoped["cases"][1]["id"] = "invented_approval"
                else:
                    scoped["cases"][0], scoped["cases"][1] = scoped["cases"][1], scoped["cases"][0]
                with self.assertRaises(SuiteError):
                    validate_policy_contrast(self.broad, scoped)

    def test_cli_returns_expected_exit_codes_and_json_without_executing_tools(self):
        for filename, expected_code, expected_value in (
            ("demo_permissive.json", 1, "allow"),
            ("demo_task_scoped.json", 0, "deny"),
        ):
            with self.subTest(name=filename):
                process = subprocess.run(
                    [sys.executable, "-m", "agent_trace_lab", "evaluate",
                     str(ROOT / "examples" / filename), "--format", "json"],
                    cwd=ROOT, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(process.returncode, expected_code)
                self.assertIn('"actual": "' + expected_value + '"', process.stdout)
                self.assertEqual(process.stderr, "")

    def test_isolated_executor_requires_exact_expected_exit_code(self):
        result = subprocess.CompletedProcess(
            ["python"], 1, stdout='{"status":"synthetic mismatch"}', stderr="",
        )
        with patch("scripts.verify_installed_wheel.subprocess.run", return_value=result):
            self.assertIn("synthetic mismatch",
                          _execute(["python"], ROOT, {}, expected_exit=1))
            with self.assertRaises(SuiteError):
                _execute(["python"], ROOT, {})


if __name__ == "__main__":
    unittest.main()
