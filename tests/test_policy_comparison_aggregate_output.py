"""ATL-004AL: share only policy delta aggregates, not case-level details."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples" / "demo_permissive.json"
CANDIDATE = ROOT / "examples" / "compare_candidate_task_guarded.json"
PRIVATE = "PRIVATE_SYNTHETIC_CASE_987112"
COUNTS = {
    "total_cases": 1, "changed": 1, "allow_to_deny": 1,
    "deny_to_allow": 0, "unchanged": 0,
    "candidate_ignored_grant_cases": 0,
}


def run_compare(*extra: str, source: Path = BASE) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_trace_lab", "compare-policies",
         str(source), "--candidate-policy", str(CANDIDATE), *extra],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


class PolicyComparisonAggregateOutputTests(unittest.TestCase):
    def test_json_summary_only_is_exact_aggregate_not_case_level(self):
        result = run_compare("--summary-only", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"summary": COUNTS})
        for omitted in ('"cases":', "unrequested_forward", "TASK_GRANT_REQUIRED",
                        "forward_email", "unrequested@example.invalid", "accuracy"):
            self.assertNotIn(omitted, result.stdout)

    def test_text_summary_is_one_original_first_line(self):
        normal = run_compare("--format", "text")
        aggregate = run_compare("--summary-only", "--format", "text")
        self.assertEqual(normal.returncode, 0, normal.stderr)
        self.assertEqual(aggregate.returncode, 0, aggregate.stderr)
        self.assertEqual(aggregate.stdout, normal.stdout.splitlines()[0] + "\n")
        self.assertEqual(len(aggregate.stdout.splitlines()), 1)
        self.assertIn("allow->deny=1", aggregate.stdout)
        self.assertNotIn("unrequested_forward", aggregate.stdout)

    def test_default_json_and_redacted_json_remain_detailed(self):
        normal = run_compare("--format", "json")
        alias = run_compare("--format", "json", "--redact-case-ids")
        aggregate_alias = run_compare(
            "--format", "json", "--summary-only", "--redact-case-ids",
        )
        self.assertEqual(normal.returncode, alias.returncode)
        self.assertEqual(alias.returncode, aggregate_alias.returncode)
        self.assertEqual(json.loads(normal.stdout)["cases"][0]["id"], "unrequested_forward")
        self.assertEqual(json.loads(alias.stdout)["cases"][0]["id"], "case_0001")
        self.assertEqual(json.loads(aggregate_alias.stdout), {"summary": COUNTS})
        self.assertNotIn("case_0001", aggregate_alias.stdout)

    def test_synthetic_private_case_id_never_serialized_in_both_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "private_suite.json"
            suite = json.loads(BASE.read_text(encoding="utf-8"))
            suite["cases"][0]["id"] = PRIVATE
            source.write_text(json.dumps(suite), encoding="utf-8")
            for fmt in ("json", "text"):
                with self.subTest(fmt=fmt):
                    response = run_compare("--summary-only", "--format", fmt, source=source)
                    self.assertEqual(response.returncode, 0, response.stderr)
                    self.assertNotIn(PRIVATE, response.stdout + response.stderr)
                    self.assertNotIn("TASK_GRANT_REQUIRED", response.stdout + response.stderr)
            self.assertIn(PRIVATE, source.read_text(encoding="utf-8"))

    def test_saved_summary_identical_to_stdout_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for fmt in ("json", "text"):
                with self.subTest(fmt=fmt):
                    target = root / f"summary-{fmt}.txt"
                    args = ("--summary-only", "--format", fmt)
                    stdout = run_compare(*args)
                    saved = run_compare(*args, "--output", str(target))
                    self.assertEqual(stdout.returncode, 0)
                    self.assertEqual(saved.returncode, 0, saved.stderr)
                    self.assertEqual(saved.stdout, "")
                    self.assertEqual(target.read_text(encoding="utf-8"), stdout.stdout)
                    original = target.read_bytes()
                    blocked = run_compare(*args, "--output", str(target))
                    self.assertEqual(blocked.returncode, 2)
                    self.assertEqual(target.read_bytes(), original)
                    replaced = run_compare(*args, "--output", str(target), "--overwrite")
                    self.assertEqual(replaced.returncode, 0, replaced.stderr)
                    self.assertEqual(target.read_bytes(), original)
                    self.assertFalse(list(root.glob(".agent-trace-compare-*.tmp")))

    def test_summary_output_cannot_overwrite_inputs(self):
        old_source = BASE.read_bytes()
        old_candidate = CANDIDATE.read_bytes()
        for path in (BASE, CANDIDATE):
            for overwrite in (False, True):
                args = ["--summary-only", "--format", "json", "--output", str(path)]
                if overwrite:
                    args.append("--overwrite")
                result = run_compare(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("refusing to overwrite", result.stderr)
                self.assertEqual(BASE.read_bytes(), old_source)
                self.assertEqual(CANDIDATE.read_bytes(), old_candidate)

    def test_valid_policy_difference_stays_exit_zero_in_both_formats(self):
        for fmt in ("json", "text"):
            res = run_compare("--summary-only", "--format", fmt)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("1", res.stdout)


if __name__ == "__main__":
    unittest.main()
