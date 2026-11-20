"""ATL-004AG: atomic caller-owned policy comparison reports."""

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

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples" / "demo_permissive.json"
CANDIDATE = ROOT / "examples" / "compare_candidate_task_guarded.json"
SENTINEL = b"PRIVATE_SYNTHETIC_UNRELATED_FILE_DO_NOT_CHANGE"


def run_compare(*, format: str = "json", output: Path | None = None,
                overwrite: bool = False, redacted: bool = False,
                baseline: Path = BASE, candidate: Path = CANDIDATE):
    args = [
        sys.executable, "-m", "agent_trace_lab", "compare-policies",
        str(baseline), "--candidate-policy", str(candidate),
        "--format", format,
    ]
    if redacted:
        args.append("--redact-case-ids")
    if output is not None:
        args.extend(["--output", str(output)])
    if overwrite:
        args.append("--overwrite")
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=15)


class PolicyReportOutputTests(unittest.TestCase):
    def test_file_bytes_equal_original_stdout_in_both_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            for fmt in ("json", "text"):
                for redacted in (False, True):
                    with self.subTest(fmt=fmt, redacted=redacted):
                        old = run_compare(format=fmt, redacted=redacted)
                        target = Path(temp) / f"report_{fmt}_{redacted}.txt"
                        new = run_compare(format=fmt, redacted=redacted, output=target)
                        self.assertEqual(old.returncode, 0, old.stderr)
                        self.assertEqual(new.returncode, 0, new.stderr)
                        self.assertEqual(new.stdout, "")
                        self.assertEqual(target.read_text(encoding="utf-8"), old.stdout)
                        if fmt == "json":
                            self.assertEqual(json.loads(target.read_bytes())["summary"]["changed"], 1)
                        else:
                            self.assertIn("allow->deny=1", target.read_text(encoding="utf-8"))

    def test_no_clobber_preserves_private_existing_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "existing_private_report.txt"
            target.write_bytes(SENTINEL)
            result = run_compare(output=target)
            self.assertEqual(result.returncode, 2)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(target.read_bytes(), SENTINEL)
            self.assertNotIn(SENTINEL.decode("utf-8"), result.stdout + result.stderr)
            self.assertEqual(list(root.glob(".agent-trace-compare-*.tmp")), [])

    def test_explicit_overwrite_only_replaces_named_regular_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "report.json"
            target.write_bytes(SENTINEL)
            untouched = root / "unrelated.txt"
            untouched.write_bytes(SENTINEL)
            result = run_compare(output=target, overwrite=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(target.read_bytes())["summary"]["changed"], 1)
            self.assertEqual(untouched.read_bytes(), SENTINEL)
            self.assertEqual(list(root.glob(".agent-trace-compare-*.tmp")), [])

    def test_input_files_never_overwritten_even_with_explicit_opt_in(self):
        baseline = BASE.read_bytes()
        candidate = CANDIDATE.read_bytes()
        for output in (BASE, CANDIDATE):
            for overwrite in (False, True):
                with self.subTest(output=output.name, overwrite=overwrite):
                    response = run_compare(output=output, overwrite=overwrite)
                    self.assertEqual(response.returncode, 2)
                    self.assertIn("refusing to overwrite", response.stderr)
                    self.assertEqual(BASE.read_bytes(), baseline)
                    self.assertEqual(CANDIDATE.read_bytes(), candidate)

    def test_redacted_report_does_not_serialize_original_case_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            suite = json.loads(BASE.read_text(encoding="utf-8"))
            suite["cases"][0]["id"] = "PRIVATE_CASE_NAME_774400"
            original = root / "private_input.json"
            original.write_text(json.dumps(suite), encoding="utf-8")
            saved = root / "redacted.json"
            response = run_compare(baseline=original, output=saved, redacted=True)
            self.assertEqual(response.returncode, 0, response.stderr)
            self.assertIn("case_0001", saved.read_text(encoding="utf-8"))
            self.assertNotIn("PRIVATE_CASE_NAME_774400", saved.read_text(encoding="utf-8"))
            self.assertNotIn("unrequested@example.invalid", saved.read_text(encoding="utf-8"))
            self.assertIn("PRIVATE_CASE_NAME_774400", original.read_text(encoding="utf-8"))

    def test_symlink_report_destination_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "unrelated.txt"
            private.write_bytes(SENTINEL)
            link = root / "report.json"
            try:
                link.symlink_to(private)
            except OSError:
                self.skipTest("symlink privilege unavailable on runner")
            for overwrite in (False, True):
                with self.subTest(overwrite=overwrite):
                    response = run_compare(output=link, overwrite=overwrite)
                    self.assertEqual(response.returncode, 2)
                    self.assertEqual(private.read_bytes(), SENTINEL)
                    self.assertTrue(link.is_symlink())

    def test_interrupted_atomic_write_never_replaces_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "report.json"
            output.write_bytes(SENTINEL)
            with patch("agent_trace_lab.cli.os.replace",
                       side_effect=OSError("PRIVATE_DESTINATION_IDENTIFIER")):
                with self.assertRaises(OSError):
                    _write_complete_output(
                        output, '{"synthetic":true}\n', overwrite=True,
                        prefix=".agent-trace-compare-",
                    )
            self.assertEqual(output.read_bytes(), SENTINEL)
            self.assertEqual(list(root.glob(".agent-trace-compare-*.tmp")), [])

    def test_cli_does_not_echo_private_low_level_io_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "PRIVATE_CLIENT_DESTINATION"
            stderr = StringIO()
            with patch("agent_trace_lab.cli._write_complete_output",
                       side_effect=OSError("PRIVATE_CLIENT_DESTINATION")):
                with redirect_stderr(stderr):
                    code = main([
                        "compare-policies", str(BASE), "--candidate-policy",
                        str(CANDIDATE), "--output", str(path),
                    ])
            self.assertEqual(code, 2)
            self.assertNotIn("PRIVATE_CLIENT_DESTINATION", stderr.getvalue())
            self.assertIn("unable to safely write policy comparison report", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
