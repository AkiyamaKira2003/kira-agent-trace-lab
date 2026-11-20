"""Regression tests for atomic and opt-in evaluation report publication."""

from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_trace_lab.cli import _write_complete_output, main
from agent_trace_lab.schema import SuiteError

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "suite.json"
MISMATCH = ROOT / "examples" / "demo_permissive.json"
SENTINEL = b"PRIVATE_EXISTING_REPORT_DO_NOT_REPLACE"


def evaluate(output: Path, *, source: Path = SOURCE,
             overwrite: bool = False, format: str = "json") -> subprocess.CompletedProcess[str]:
    argv = [
        sys.executable, "-m", "agent_trace_lab", "evaluate", str(source),
        "--format", format, "--output", str(output),
    ]
    if overwrite:
        argv.append("--overwrite")
    return subprocess.run(
        argv, cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


class EvaluationOutputSafetyTests(unittest.TestCase):
    def test_first_publication_and_second_identical_attempt_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            first = evaluate(target)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, "")
            original = target.read_bytes()
            self.assertEqual(json.loads(original)["summary"]["matched"], 8)
            second = evaluate(target)
            self.assertEqual(second.returncode, 2)
            self.assertIn("already exists", second.stderr)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(Path(tmp).glob(".agent-trace-report-*.tmp")), [])

    def test_existing_unrelated_report_survives_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            target = folder / "private_report.txt"
            target.write_bytes(SENTINEL)
            other = folder / "unrelated.txt"
            other.write_bytes(SENTINEL)
            run = evaluate(target, format="text")
            self.assertEqual(run.returncode, 2)
            self.assertEqual(target.read_bytes(), SENTINEL)
            self.assertEqual(other.read_bytes(), SENTINEL)
            self.assertNotIn(SENTINEL.decode(), run.stdout + run.stderr)

    def test_opt_in_overwrite_only_replaces_named_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            target = folder / "report.json"
            target.write_bytes(SENTINEL)
            other = folder / "unrelated.txt"
            other.write_bytes(SENTINEL)
            result = evaluate(target, overwrite=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(target.read_bytes())["summary"]["matched"], 8)
            self.assertEqual(other.read_bytes(), SENTINEL)
            self.assertEqual(list(folder.glob(".agent-trace-report-*.tmp")), [])

    def test_mismatch_exit_one_and_valid_report_still_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "mismatched.json"
            mismatch = evaluate(target, source=MISMATCH)
            self.assertEqual(mismatch.returncode, 1)
            self.assertEqual(json.loads(target.read_bytes())["cases"][0]["actual"], "allow")
            before = target.read_bytes()
            self.assertEqual(evaluate(target, source=MISMATCH).returncode, 2)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(evaluate(target, source=MISMATCH, overwrite=True).returncode, 1)

    def test_source_cannot_be_overwritten_even_explicitly(self):
        original = SOURCE.read_bytes()
        for force in (False, True):
            with self.subTest(force=force):
                result = evaluate(SOURCE, source=SOURCE, overwrite=force)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(SOURCE.read_bytes(), original)

    def test_symbolic_link_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = folder / "private.txt"
            original.write_bytes(SENTINEL)
            alias = folder / "report.json"
            try:
                alias.symlink_to(original)
            except OSError:
                self.skipTest("Windows runner lacks symlink privilege")
            for force in (False, True):
                with self.subTest(force=force):
                    result = evaluate(alias, overwrite=force)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(original.read_bytes(), SENTINEL)
                    self.assertTrue(alias.is_symlink())

    def test_mocked_symlink_guard_does_not_require_privilege(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            with patch("agent_trace_lab.cli.Path.is_symlink", return_value=True):
                with self.assertRaisesRegex(SuiteError, "symbolic-link"):
                    _write_complete_output(
                        target, "fixture", overwrite=True,
                        prefix=".agent-trace-report-",
                    )
            self.assertFalse(target.exists())

    def test_partial_write_never_exposes_report_or_replaces_old_bytes(self):
        real_create = tempfile.NamedTemporaryFile

        class PartialFailure:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.name = wrapped.name

            def __enter__(self):
                self.wrapped.__enter__()
                return self

            def __exit__(self, kind, value, tb):
                return self.wrapped.__exit__(kind, value, tb)

            def write(self, text):
                self.wrapped.write(text[:7])
                self.wrapped.flush()
                raise OSError("synthetic interrupted report write")

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for overwrite in (False, True):
                with self.subTest(overwrite=overwrite):
                    target = folder / ("forced.txt" if overwrite else "fresh.txt")
                    if overwrite:
                        target.write_bytes(SENTINEL)
                    with patch(
                        "agent_trace_lab.cli.tempfile.NamedTemporaryFile",
                        side_effect=lambda *args, **kwargs: PartialFailure(
                            real_create(*args, **kwargs)
                        ),
                    ):
                        with self.assertRaisesRegex(OSError, "interrupted"):
                            _write_complete_output(
                                target, "synthetic report", overwrite=overwrite,
                                prefix=".agent-trace-report-",
                            )
                    if overwrite:
                        self.assertEqual(target.read_bytes(), SENTINEL)
                    else:
                        self.assertFalse(target.exists())
                    self.assertEqual(list(folder.glob(".agent-trace-report-*.tmp")), [])

    def test_failure_diagnostics_do_not_expose_private_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "PRIVATE_CLIENT_NAME_DO_NOT_ECHO.json"
            diagnostics = StringIO()
            with patch(
                "agent_trace_lab.cli._write_complete_output",
                side_effect=OSError(f"failed: {target} SECRET_ARGUMENT_MARKER"),
            ):
                with redirect_stderr(diagnostics):
                    code = main(["evaluate", str(SOURCE), "--output", str(target)])
            self.assertEqual(code, 2)
            self.assertNotIn("PRIVATE_CLIENT_NAME_DO_NOT_ECHO", diagnostics.getvalue())
            self.assertNotIn("SECRET_ARGUMENT_MARKER", diagnostics.getvalue())
            self.assertIn("unable to safely write evaluation report", diagnostics.getvalue())


if __name__ == "__main__":
    unittest.main()
