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
EXAMPLE = ROOT / "examples" / "suite.json"


class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = load_suite(EXAMPLE)

    def test_examples_are_reproducibly_classified(self) -> None:
        first = evaluate_suite(self.suite)
        self.assertEqual(first, evaluate_suite(copy.deepcopy(self.suite)))
        self.assertEqual(first["summary"]["matched"], 8)
        self.assertEqual(first["summary"]["confusion"], {"tp": 5, "tn": 3, "fp": 0, "fn": 0})
        self.assertEqual(first["summary"]["accuracy"], 1)

    def test_exact_prefix_and_path_traversal(self) -> None:
        for path, code in [
            ("/workspace/docs2/secret", "PATH_OUTSIDE_ROOT"),
            ("/workspace/docs/../secret", "PATH_INVALID"),
            ("/workspace/docs\\..\\secret", "PATH_INVALID"),
            ("C:\\workspace\\docs\\file", "PATH_INVALID"),
            ("/workspace/docs//x", "PATH_INVALID"),
            ("relative/file", "PATH_INVALID"),
        ]:
            with self.subTest(path=path):
                case = self.suite["cases"][1]
                case["trace"][0]["arguments"]["path"] = path
                report = evaluate_suite(self.suite)
                self.assertEqual(report["cases"][1]["violations"][0]["code"], code)
        self.assertTrue(evaluate_suite(load_suite(EXAMPLE))["cases"][1]["matched"])

    def test_url_scope_and_host_spoofing(self) -> None:
        for url, code in [
            ("https://docs.example.org.attacker.test/", "HOST_NOT_ALLOWED"),
            ("https://attacker.test@docs.example.org/", "URL_INVALID"),
            ("http://docs.example.org/", "URL_INVALID"),
            ("https://docs.example.org:444/", "URL_INVALID"),
            ("https://docs.example.org\\@evil.test/", "URL_INVALID"),
            ("javascript:alert(1)", "URL_INVALID"),
        ]:
            with self.subTest(url=url):
                case = self.suite["cases"][2]
                case["trace"][0]["arguments"]["url"] = url
                report = evaluate_suite(self.suite)
                self.assertEqual(report["cases"][2]["violations"][0]["code"], code)

    def test_missing_arguments_fail_closed(self) -> None:
        self.suite["cases"][1]["trace"][0]["arguments"] = {}
        self.assertEqual(evaluate_suite(self.suite)["cases"][1]["violations"][0]["code"], "MISSING_ARGUMENT")

    def test_false_positive_false_negative_counts(self) -> None:
        self.suite["cases"][0]["expected"] = "deny"
        self.suite["cases"][3]["expected"] = "allow"
        summary = evaluate_suite(self.suite)["summary"]
        self.assertEqual(summary["confusion"], {"tp": 4, "tn": 2, "fp": 1, "fn": 1})
        self.assertEqual(summary["matched"], 6)

    def test_empty_trace_is_allow_not_automatic_security_success(self) -> None:
        self.suite["cases"][3]["trace"] = []
        result = evaluate_suite(self.suite)["cases"][3]
        self.assertEqual((result["actual"], result["matched"]), ("allow", False))

    def test_unknown_fields_are_rejected(self) -> None:
        self.suite["cases"][0]["trace"][0]["python_code"] = "print('hi')"
        with self.assertRaises(SuiteError):
            evaluate_suite(self.suite)

    def test_policy_rejects_incomplete_constraints(self) -> None:
        del self.suite["policy"]["tools"]["files.read"]["allowed_roots"]
        with self.assertRaises(SuiteError):
            validate_suite(self.suite)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf-8")
            with self.assertRaisesRegex(SuiteError, "duplicate JSON"):
                load_suite(path)

    def test_non_json_nan_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nan.json"
            path.write_text('{"score":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(SuiteError, "non-JSON"):
                load_suite(path)

    def test_zero_denominator_metrics_are_null(self) -> None:
        safe = self.suite["cases"][0]
        self.suite["cases"] = [safe]
        summary = evaluate_suite(self.suite)["summary"]
        self.assertEqual(summary["confusion"], {"tp": 0, "tn": 1, "fp": 0, "fn": 0})
        self.assertIsNone(summary["deny_precision"])
        self.assertIsNone(summary["deny_recall"])

    def test_tool_name_is_case_sensitive(self) -> None:
        self.suite["cases"][0]["trace"][0]["tool"] = "Docs.Search"
        report = evaluate_suite(self.suite)
        self.assertEqual(report["cases"][0]["violations"][0]["code"], "TOOL_NOT_ALLOWED")

    def test_invalid_host_policy_is_rejected(self) -> None:
        self.suite["policy"]["tools"]["net.fetch"]["allowed_hosts"] = ["docs.example.org.evil/path"]
        with self.assertRaises(SuiteError):
            evaluate_suite(self.suite)

    def test_cli_exit_one_for_label_mismatch(self) -> None:
        self.suite["cases"][0]["expected"] = "deny"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mismatch.json"
            path.write_text(json.dumps(self.suite), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "agent_trace_lab", "evaluate", str(path), "--format", "json"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["summary"]["matched"], 7)

    def test_file_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.json"
            path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
            with self.assertRaisesRegex(SuiteError, "exceeds"):
                load_suite(path)

    def test_cli_json_and_failure_exit_codes(self) -> None:
        valid = subprocess.run(
            [sys.executable, "-m", "agent_trace_lab", "evaluate", str(EXAMPLE), "--format", "json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(json.loads(valid.stdout)["summary"]["matched"], 8)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("not json", encoding="utf-8")
            bad = subprocess.run(
                [sys.executable, "-m", "agent_trace_lab", "evaluate", str(path)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(bad.returncode, 2)
            overwrite = subprocess.run(
                [sys.executable, "-m", "agent_trace_lab", "evaluate", str(EXAMPLE), "--output", str(EXAMPLE)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(overwrite.returncode, 2)


if __name__ == "__main__":
    unittest.main()
