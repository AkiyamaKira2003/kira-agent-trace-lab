"""Negative/positive controls for a source-date-pinned two-wheel comparison."""

from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from agent_trace_lab.schema import SuiteError
from scripts.verify_installed_wheel import REQUIRED_WHEEL_MEMBERS, source_project_version
from scripts.verify_reproducible_wheel import (
    EXPECTED_WHEEL_NAME, build_twice, compare_wheels,
    get_git_commit_epoch, validate_epoch,
)


def synthetic_wheel(folder: Path, *, altered: bool = False,
                    omitted: str | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / EXPECTED_WHEEL_NAME
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name in sorted(REQUIRED_WHEEL_MEMBERS):
            if name == omitted:
                continue
            data = b"same contents" if not altered or name != "agent_trace_lab/cli.py" else b"changed content"
            z.writestr(name, data)
    return path


class ReproducibleWheelTests(unittest.TestCase):
    def test_expected_wheel_filename_tracks_source_metadata(self):
        self.assertEqual(
            EXPECTED_WHEEL_NAME,
            f"kira_agent_trace_lab-{source_project_version()}-py3-none-any.whl",
        )

    def test_stable_synthetic_wheels_match_within_environment(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = compare_wheels(synthetic_wheel(root / "a"),
                                    synthetic_wheel(root / "b"))
            self.assertEqual(result["status"], "WITHIN_ENVIRONMENT_BYTE_IDENTICAL_WHEELS")
            self.assertEqual(len(result["wheel_sha256"]), 64)
            self.assertFalse(result["cross_platform_byte_identity_claimed"])
            self.assertFalse(result["recorded_agent_actions_executed"])

    def test_different_bytes_under_same_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(SuiteError, "differ"):
                compare_wheels(synthetic_wheel(root / "a"),
                               synthetic_wheel(root / "b", altered=True))

    def test_different_members_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaisesRegex(SuiteError, "missing"):
                compare_wheels(synthetic_wheel(root / "a"),
                               synthetic_wheel(root / "b", omitted="agent_trace_lab/cli.py"))

    def test_wrong_version_rejected_even_if_bytes_match(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = synthetic_wheel(root / "a")
            b = synthetic_wheel(root / "b")
            b.rename(b.with_name("kira_agent_trace_lab-0.4.0-py3-none-any.whl"))
            with self.assertRaisesRegex(SuiteError, "unexpected"):
                compare_wheels(a, b.with_name("kira_agent_trace_lab-0.4.0-py3-none-any.whl"))

    def test_epoch_validation_rejects_invalid_and_too_old_values(self):
        self.assertEqual(validate_epoch("1795201363"), "1795201363")
        for value in ("", "0", "abc", "-123456789", "315532799",
                      "4102444801", "1795201363\n", 1795201363, None):
            with self.subTest(epoch=value):
                with self.assertRaises(SuiteError):
                    validate_epoch(value)

    def test_git_commit_timestamp_is_validated(self):
        result = subprocess.CompletedProcess(["git"], 0, stdout="1795201363\n", stderr="")
        with patch("scripts.verify_reproducible_wheel.subprocess.run", return_value=result):
            self.assertEqual(get_git_commit_epoch(), "1795201363")
        for bad in (
            subprocess.CompletedProcess(["git"], 1, stdout="", stderr="no commit"),
            subprocess.CompletedProcess(["git"], 0, stdout="INVALID", stderr=""),
        ):
            with patch("scripts.verify_reproducible_wheel.subprocess.run", return_value=bad):
                with self.assertRaises(SuiteError):
                    get_git_commit_epoch()

    def test_build_failure_does_not_leak_raw_subprocess_output(self):
        failed = subprocess.CompletedProcess(
            ["python"], 1, stdout="PRIVATE DATA IN BUILD STDOUT",
            stderr="UNREDACTED SOURCE PATH AND TOKENS",
        )
        with patch("scripts.verify_reproducible_wheel.get_git_commit_epoch",
                   return_value="1795201363"):
            with patch("scripts.verify_reproducible_wheel.subprocess.run", return_value=failed):
                with self.assertRaises(SuiteError) as ctx:
                    build_twice()
        self.assertNotIn("PRIVATE DATA", str(ctx.exception))
        self.assertNotIn("UNREDACTED", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
