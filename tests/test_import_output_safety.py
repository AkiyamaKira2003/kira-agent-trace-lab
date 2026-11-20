"""ATL-004R: importer output is caller-owned and must not clobber silently."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_trace_lab.cli import _write_import_suite
from agent_trace_lab.schema import SuiteError, load_suite

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ("import-otlp", "otlp_spans.json", "suite.json"),
    ("import-swe", "swe_recorded_row_synthetic.json", "swe_structural_policy.json"),
    ("import-agentdojo", "agentdojo_recorded_synthetic.json", "agentdojo_policy_simulated_scope.json"),
)
SENTINEL = "SELF_AUTHORED_OUTPUT_SHOULD_STAY_UNCHANGED"


def invoke(command: str, source: str, policy: str, dest: Path,
           *, overwrite: bool = False) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable, "-m", "agent_trace_lab", command,
        str(ROOT / "examples" / source), "--policy-suite",
        str(ROOT / "examples" / policy), "--case-id", "synthetic_demo",
        "--expected", "allow", "--output", str(dest),
    ]
    if overwrite:
        args.append("--overwrite")
    return subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


class ImportOutputSafetyTests(unittest.TestCase):
    def test_first_write_succeeds_but_second_does_not_replace(self) -> None:
        for command, source, policy in SOURCES:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "imported.json"
                first = invoke(command, source, policy, target)
                self.assertEqual(first.returncode, 0, first.stderr)
                original = target.read_bytes()
                self.assertEqual(len(load_suite(target)["cases"]), 1)
                second = invoke(command, source, policy, target)
                self.assertEqual(second.returncode, 2)
                self.assertIn("already exists", second.stderr)
                self.assertEqual(target.read_bytes(), original)

    def test_existing_unrelated_file_is_preserved_by_default(self) -> None:
        for command, source, policy in SOURCES:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "existing.json"
                target.write_text(SENTINEL, encoding="utf-8")
                result = invoke(command, source, policy, target)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(target.read_text(encoding="utf-8"), SENTINEL)
                self.assertNotIn(SENTINEL, result.stderr)

    def test_explicit_overwrite_replaces_only_named_file(self) -> None:
        for command, source, policy in SOURCES:
            with self.subTest(command=command), tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / "existing.json"
                target.write_text(SENTINEL, encoding="utf-8")
                other = Path(tmp) / "other.txt"
                other.write_text(SENTINEL, encoding="utf-8")
                result = invoke(command, source, policy, target, overwrite=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(len(load_suite(target)["cases"]), 1)
                self.assertEqual(other.read_text(encoding="utf-8"), SENTINEL)
                self.assertEqual(list(Path(tmp).glob(".agent-trace-import-*.tmp")), [])

    def test_hardlink_alias_of_unrelated_file_stays_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_file = Path(tmp) / "original.txt"
            source_file.write_text(SENTINEL, encoding="utf-8")
            alias = Path(tmp) / "alias.json"
            try:
                os.link(source_file, alias)
            except OSError:
                self.skipTest("hardlink creation not permitted on runner")
            command, source, policy = SOURCES[0]
            no_force = invoke(command, source, policy, alias)
            self.assertEqual(no_force.returncode, 2)
            self.assertEqual(source_file.read_text(encoding="utf-8"), SENTINEL)
            explicit = invoke(command, source, policy, alias, overwrite=True)
            self.assertEqual(explicit.returncode, 0, explicit.stderr)
            self.assertEqual(source_file.read_text(encoding="utf-8"), SENTINEL)
            self.assertEqual(len(load_suite(alias)["cases"]), 1)

    def test_symlink_output_is_refused_without_following(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.txt"
            original.write_text(SENTINEL, encoding="utf-8")
            link = Path(tmp) / "output.json"
            try:
                link.symlink_to(original)
            except OSError:
                self.skipTest("symlink creation not permitted on runner")
            for command, source, policy in SOURCES:
                with self.subTest(command=command):
                    for overwrite in (False, True):
                        result = invoke(command, source, policy, link, overwrite=overwrite)
                        self.assertEqual(result.returncode, 2)
                        self.assertEqual(original.read_text(encoding="utf-8"), SENTINEL)
                        self.assertTrue(link.is_symlink())

    def test_source_file_is_protected_even_with_explicit_overwrite(self) -> None:
        for command, source, policy in SOURCES:
            path = ROOT / "examples" / source
            original = path.read_bytes()
            result = invoke(command, source, policy, path, overwrite=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), original)

    def test_symbolic_link_overwrite_guard_without_symlink_privilege(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "output.json"
            with patch("agent_trace_lab.cli.Path.is_symlink", return_value=True):
                with self.assertRaisesRegex(SuiteError, "symbolic-link"):
                    _write_import_suite(target, {"synthetic": True}, overwrite=True)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
