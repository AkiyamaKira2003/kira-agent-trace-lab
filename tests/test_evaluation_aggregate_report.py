"""Privacy-limited aggregate-only reports for caller-labeled trace cases."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.schema import load_suite

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "suite.json"
MISMATCH = ROOT / "examples" / "demo_permissive.json"
PRIVATE_MARKER = "PRIVATE_CASE_OR_TOOL_7561234"


def run_report(source: Path, *, mode: str = "json", extra: tuple[str, ...] = ()):
    return subprocess.run(
        [sys.executable, "-m", "agent_trace_lab", "evaluate", str(source),
         "--summary-only", "--format", mode, *extra],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


class AggregateReportTests(unittest.TestCase):
    def test_json_has_only_counts_and_explicit_unverified_label_basis(self):
        result = run_report(SOURCE)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {
            "schema_version", "label_basis",
            "verified_real_world_security_metrics", "summary",
        })
        self.assertEqual(data["label_basis"], "caller_supplied_not_independently_verified")
        self.assertFalse(data["verified_real_world_security_metrics"])
        self.assertEqual(data["summary"], {
            "total_cases": 8, "matched_fixture_labels": 8,
            "mismatched_fixture_labels": 0,
            "confusion": {"tp": 5, "tn": 3, "fp": 0, "fn": 0},
        })
        self.assertNotIn("accuracy", result.stdout)
        self.assertNotIn('"cases"', result.stdout)

    def test_text_contains_counts_and_no_per_case_details(self):
        result = run_report(SOURCE, mode="text")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("8/8", result.stdout)
        self.assertIn("No independently verified real-world security metrics.", result.stdout)
        self.assertNotIn("PASS ", result.stdout)
        self.assertNotIn("violation", result.stdout)
        self.assertEqual(result.stdout, run_report(SOURCE, mode="text").stdout)

    def test_aggregate_omits_private_case_tool_and_arguments(self):
        original = load_suite(SOURCE)
        modified = copy.deepcopy(original)
        modified["cases"][0]["id"] = PRIVATE_MARKER
        modified["cases"][0]["trace"][0]["tool"] = PRIVATE_MARKER
        modified["cases"][0]["trace"][0]["arguments"]["private"] = PRIVATE_MARKER
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private_suite.json"
            path.write_text(json.dumps(modified), encoding="utf-8")
            before = path.read_bytes()
            for mode in ("json", "text"):
                with self.subTest(mode=mode):
                    run = run_report(path, mode=mode)
                    self.assertIn(run.returncode, (0, 1), run.stderr)
                    self.assertNotIn(PRIVATE_MARKER, run.stdout + run.stderr)
                    self.assertNotIn("TOOL_NOT_ALLOWED", run.stdout)
            self.assertEqual(path.read_bytes(), before)

    def test_mismatched_fixture_retains_exit_one(self):
        run = run_report(MISMATCH)
        self.assertEqual(run.returncode, 1, run.stderr)
        data = json.loads(run.stdout)
        self.assertEqual(data["summary"]["total_cases"], 1)
        self.assertEqual(data["summary"]["matched_fixture_labels"], 0)
        self.assertEqual(data["summary"]["mismatched_fixture_labels"], 1)
        self.assertNotIn("unrequested_forward", run.stdout)
        self.assertNotIn("unrequested@example.invalid", run.stdout)

    def test_saved_aggregate_respects_no_clobber_and_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            output = folder / "summary.json"
            protected = folder / "unrelated.txt"
            protected.write_text("PRIVATE_UNRELATED_SENTINEL", encoding="utf-8")
            first = run_report(SOURCE, extra=("--output", str(output)))
            self.assertEqual(first.returncode, 0, first.stderr)
            expected = output.read_bytes()
            self.assertEqual(json.loads(expected)["summary"]["total_cases"], 8)
            self.assertEqual(run_report(SOURCE, extra=("--output", str(output))).returncode, 2)
            self.assertEqual(output.read_bytes(), expected)
            self.assertEqual(
                run_report(SOURCE, extra=("--output", str(output), "--overwrite")).returncode,
                0,
            )
            self.assertEqual(output.read_bytes(), expected)
            self.assertEqual(protected.read_text(encoding="utf-8"), "PRIVATE_UNRELATED_SENTINEL")

    def test_invalid_input_failure_avoids_secret_marker(self):
        invalid = load_suite(SOURCE)
        invalid["cases"][0][PRIVATE_MARKER] = "synthetic private"
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "invalid.json"
            output = Path(directory) / "should_not_exist.json"
            input_file.write_text(json.dumps(invalid), encoding="utf-8")
            result = run_report(input_file, extra=("--output", str(output)))
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(PRIVATE_MARKER, result.stdout + result.stderr)
            self.assertFalse(output.exists())

    def test_default_json_behavior_is_unchanged(self):
        result = subprocess.run(
            [sys.executable, "-m", "agent_trace_lab", "evaluate",
             str(SOURCE), "--format", "json"],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(len(report["cases"]), 8)
        self.assertEqual(report["summary"]["matched"], 8)


if __name__ == "__main__":
    unittest.main()
