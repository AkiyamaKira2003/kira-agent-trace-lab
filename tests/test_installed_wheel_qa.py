"""Security and correctness controls for installed-wheel reproducibility checks."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from agent_trace_lab.schema import SuiteError
from scripts.verify_installed_wheel import (
    REQUIRED_WHEEL_MEMBERS, _execute, validate_evaluation, wheel_members,
)


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


if __name__ == "__main__":
    unittest.main()
