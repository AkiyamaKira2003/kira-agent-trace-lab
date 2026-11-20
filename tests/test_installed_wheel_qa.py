"""Security and correctness controls for installed-wheel reproducibility checks."""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from agent_trace_lab.schema import SuiteError
from agent_trace_lab.engine import evaluate_suite
from agent_trace_lab.schema import load_suite
from scripts.verify_installed_wheel import (
    REQUIRED_WHEEL_MEMBERS, _execute, validate_evaluation, wheel_members,
    installed_console_path, validate_console_equivalence,
)

ROOT = Path(__file__).resolve().parents[1]


def make_wheel(directory: Path, *, members: list[str] | None = None) -> Path:
    path = directory / "kira_agent_trace_lab-0.5.0.dev0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name in members if members is not None else sorted(REQUIRED_WHEEL_MEMBERS):
            archive.writestr(name, "# harmless synthetic placeholder\n")
    return path


class InstalledWheelQATests(unittest.TestCase):
    def test_expected_package_members_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = make_wheel(Path(directory))
            self.assertEqual(wheel_members(path), set(REQUIRED_WHEEL_MEMBERS))

    def test_script_and_local_sensitive_artifacts_not_packaged(self):
        for extra in ("scripts/verify_installed_wheel.py",
                      "docs/agentdojo_argument_shapes.json",
                      "artifacts/private.json", "examples/private.json", ".env"):
            with self.subTest(member=extra), tempfile.TemporaryDirectory() as directory:
                path = make_wheel(Path(directory), members=[*REQUIRED_WHEEL_MEMBERS, extra])
                if extra == ".env":
                    # .env is directly rejected as a forbidden suffix
                    pass
                with self.assertRaises(SuiteError):
                    wheel_members(path)

    def test_traversal_and_absolute_members_rejected(self):
        for extra in ("../private.txt", "/absolute/path"):
            with self.subTest(member=extra), tempfile.TemporaryDirectory() as directory:
                path = make_wheel(Path(directory), members=[*REQUIRED_WHEEL_MEMBERS, extra])
                with self.assertRaisesRegex(SuiteError, "unsafe"):
                    wheel_members(path)

    def test_windows_separator_rejected_if_exposed_by_zip_reader(self):
        # Windows ZipInfo normalizes real archive backslashes to '/'. Stub
        # namelist to exercise our explicit fallback defense nonetheless.
        with tempfile.TemporaryDirectory() as directory:
            path = make_wheel(Path(directory))
            with patch("scripts.verify_installed_wheel.zipfile.ZipFile") as reader:
                reader.return_value.__enter__.return_value.namelist.return_value = [
                    *REQUIRED_WHEEL_MEMBERS, "agent_trace_lab" + chr(92) + "secret.py",
                ]
                with self.assertRaisesRegex(SuiteError, "unsafe"):
                    wheel_members(path)

    def test_missing_required_cli_or_importer_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            members = sorted(REQUIRED_WHEEL_MEMBERS - {"agent_trace_lab/agentdojo.py"})
            path = make_wheel(Path(directory), members=members)
            with self.assertRaisesRegex(SuiteError, "missing"):
                wheel_members(path)

    def test_malformed_or_nonwheel_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "kira_agent_trace_lab-0.5.0.dev0-py3-none-any.whl"
            bad.write_bytes(b"not a zip archive")
            with self.assertRaisesRegex(SuiteError, "valid wheel"):
                wheel_members(bad)
            bad.rename(Path(directory) / "something_else.zip")
            with self.assertRaisesRegex(SuiteError, "wheel path"):
                wheel_members(Path(directory) / "something_else.zip")

    def test_json_summary_require_exact_fixture_matches(self):
        validate_evaluation({"summary": {"total": 8, "matched": 8}}, 8)
        for bad in (
            None, {}, {"summary": None},
            {"summary": {"total": 8, "matched": 7}},
            {"summary": {"total": True, "matched": 8}},
            {"summary": {"total": 8, "matched": "8"}},
        ):
            with self.subTest(value=bad):
                with self.assertRaises(SuiteError):
                    validate_evaluation(bad, 8)

    def test_failed_cli_does_not_leak_subprocess_output(self):
        failing = subprocess.CompletedProcess(
            args=["python"], returncode=2, stdout="SECRET-SENTINEL",
            stderr="PRIVATE-RECIPIENT-ADDRESS",
        )
        with patch("scripts.verify_installed_wheel.subprocess.run", return_value=failing):
            with self.assertRaises(SuiteError) as error:
                _execute(["python"], Path("."), {})
        self.assertNotIn("SECRET-SENTINEL", str(error.exception))
        self.assertNotIn("PRIVATE-RECIPIENT-ADDRESS", str(error.exception))

    def test_console_launcher_is_found_under_pip_target_bin_on_both_platforms(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "bin").mkdir()
            windows = site / "bin" / "agent-trace-lab.exe"
            unix = site / "bin" / "agent-trace-lab"
            windows.write_bytes(b"synthetic executable placeholder")
            unix.write_bytes(b"#!/usr/bin/env python\n")
            unix.chmod(0o755)
            self.assertEqual(installed_console_path(site, "nt"), windows)
            with patch("scripts.verify_installed_wheel.os.access", return_value=True):
                self.assertEqual(installed_console_path(site, "posix"), unix)

    def test_missing_or_unsupported_console_launcher_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            with self.assertRaisesRegex(SuiteError, "absent or unsafe"):
                installed_console_path(site, "nt")
            with self.assertRaisesRegex(SuiteError, "unsupported"):
                installed_console_path(site, "unexpected_platform")
            (site / "bin").mkdir()
            unix = site / "bin" / "agent-trace-lab"
            unix.write_bytes(b"not executable")
            with patch("scripts.verify_installed_wheel.os.access", return_value=False):
                with self.assertRaisesRegex(SuiteError, "absent or unsafe"):
                    installed_console_path(site, "posix")

    def test_console_vs_module_verdict_comparison_rejects_false_equivalence(self):
        permissive = evaluate_suite(load_suite(ROOT / "examples" / "demo_permissive.json"))
        scoped = evaluate_suite(load_suite(ROOT / "examples" / "demo_task_scoped.json"))
        validate_console_equivalence(permissive, scoped,
                                     copy.deepcopy(permissive), copy.deepcopy(scoped))
        for section, change in (
            ("permissive", "schema_version"),
            ("permissive", "summary"),
            ("scoped", "schema_version"),
            ("scoped", "summary"),
        ):
            with self.subTest(section=section, field=change):
                observed_broad = copy.deepcopy(permissive)
                observed_scoped = copy.deepcopy(scoped)
                altered = observed_broad if section == "permissive" else observed_scoped
                if change == "schema_version":
                    altered[change] = "other"
                else:
                    altered["summary"]["accuracy"] = -1
                with self.assertRaises(SuiteError):
                    validate_console_equivalence(permissive, scoped,
                                                 observed_broad, observed_scoped)


if __name__ == "__main__":
    unittest.main()
