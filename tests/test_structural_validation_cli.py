"""ATL-004AM: structural-only suite preflight, never recorded action evaluation."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_trace_lab.cli import main
from agent_trace_lab.schema import load_suite

ROOT = Path(__file__).resolve().parents[1]
NORMAL = ROOT / "examples" / "suite.json"
GUARDED = ROOT / "examples" / "demo_task_scoped.json"
MARKER = "PRIVATE_SYNTHETIC_IDENTIFIER_91421"


def invoke(source: Path, *extras: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_trace_lab", "validate", str(source), *extras],
        cwd=ROOT, text=True, capture_output=True, timeout=15,
    )


class StructuralValidationCliTests(unittest.TestCase):
    def test_both_schemas_report_only_counts_without_assessing_labels(self):
        for source in (NORMAL, GUARDED):
            with self.subTest(source=source.name):
                original = load_suite(source)
                actual = invoke(source, "--format", "json")
                self.assertEqual(actual.returncode, 0, actual.stderr)
                self.assertEqual(json.loads(actual.stdout), {
                    "schema_version": original["schema_version"],
                    "case_count": len(original["cases"]),
                    "recorded_call_count": sum(len(c["trace"]) for c in original["cases"]),
                    "policy_tool_count": len(original["policy"]["tools"]),
                    "guarded_tool_count": len(original["policy"].get("task_guarded_tools", [])),
                    "evaluation_performed": False,
                })
                for case in original["cases"]:
                    self.assertNotIn(case["id"], actual.stdout)
                self.assertNotIn('"cases":', actual.stdout)
                self.assertNotIn('"trace":', actual.stdout)
                self.assertNotIn('"expected":', actual.stdout)
                self.assertNotIn('"actual":', actual.stdout)

    def test_text_is_single_structural_line(self):
        result = invoke(NORMAL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn("Valid suite schema 1.0", result.stdout)
        self.assertIn("No policy evaluation or tool execution.", result.stdout)
        self.assertNotIn("normal_search", result.stdout)

    def test_code_path_never_evaluates_a_policy(self):
        printed = StringIO()
        with patch("agent_trace_lab.cli.evaluate_suite",
                   side_effect=AssertionError("evaluator invoked")):
            with patch("agent_trace_lab.cli.compare_policies",
                       side_effect=AssertionError("comparison invoked")):
                with redirect_stdout(printed):
                    code = main(["validate", str(NORMAL), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(printed.getvalue())["evaluation_performed"])

    def test_private_case_tool_ids_arguments_never_serialized(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "private.json"
            suite = copy.deepcopy(load_suite(NORMAL))
            suite["cases"][0]["id"] = MARKER
            suite["cases"][0]["trace"][0]["tool"] = MARKER
            suite["cases"][0]["trace"][0]["arguments"]["query"] = MARKER
            source.write_text(json.dumps(suite), encoding="utf-8")
            for fmt in ("json", "text"):
                with self.subTest(fmt=fmt):
                    result = invoke(source, "--format", fmt)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn(MARKER, result.stdout + result.stderr)
            self.assertIn(MARKER, source.read_text(encoding="utf-8"))

    def test_invalid_suite_rejects_missing_and_unknown_private_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            missing = root / (MARKER + ".json")
            result = invoke(missing, "--format", "json")
            self.assertEqual(result.returncode, 2)
            self.assertIn("filesystem I/O failure", result.stderr)
            self.assertNotIn(MARKER, result.stdout + result.stderr)
            suite = load_suite(NORMAL)
            suite["cases"][0][MARKER] = "untrusted private value"
            malformed = root / "invalid.json"
            malformed.write_text(json.dumps(suite), encoding="utf-8")
            result = invoke(malformed)
            self.assertEqual(result.returncode, 2)
            self.assertIn("unexpected_count=1", result.stderr)
            self.assertNotIn(MARKER, result.stdout + result.stderr)
            self.assertFalse(any(p.name.endswith(".tmp") for p in root.iterdir()))

    def test_atomic_report_no_clobber_and_input_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "counts.json"
            baseline = NORMAL.read_bytes()
            args = ("--format", "json", "--output", str(output))
            first = invoke(NORMAL, *args)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, "")
            stored = output.read_bytes()
            self.assertEqual(json.loads(stored)["evaluation_performed"], False)
            second = invoke(NORMAL, *args)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output.read_bytes(), stored)
            third = invoke(NORMAL, *args, "--overwrite")
            self.assertEqual(third.returncode, 0, third.stderr)
            self.assertEqual(output.read_bytes(), stored)
            for overwrite in (False, True):
                source_args = ("--output", str(NORMAL)) + (("--overwrite",) if overwrite else ())
                refused = invoke(NORMAL, *source_args)
                self.assertEqual(refused.returncode, 2)
                self.assertIn("refusing to overwrite input suite", refused.stderr)
            self.assertEqual(NORMAL.read_bytes(), baseline)
            self.assertFalse(list(root.glob(".agent-trace-validate-*.tmp")))

    def test_private_destination_filesystem_error_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parent = root / MARKER
            sentinel = b"UNRELATED_SYNTHETIC_FILE"
            parent.write_bytes(sentinel)
            result = invoke(NORMAL, "--output", str(parent / "report.json"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("unable to safely write structural validation report", result.stderr)
            self.assertNotIn(MARKER, result.stdout + result.stderr)
            self.assertEqual(parent.read_bytes(), sentinel)

    def test_symlink_output_refused_even_with_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = root / "original.txt"
            actual.write_bytes(b"SENTINEL")
            link = root / "linked.json"
            try:
                link.symlink_to(actual)
            except OSError:
                self.skipTest("symlink privilege unavailable on runner")
            for overwrite in (False, True):
                args = ("--output", str(link)) + (("--overwrite",) if overwrite else ())
                result = invoke(NORMAL, *args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(actual.read_bytes(), b"SENTINEL")


if __name__ == "__main__":
    unittest.main()
