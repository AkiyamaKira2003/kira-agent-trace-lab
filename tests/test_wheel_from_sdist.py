"""Bounded cross-platform source archive -> wheel CI helper tests."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_trace_lab.schema import SuiteError
from scripts.verify_installed_wheel import source_project_version
from scripts.wheel_from_sdist import build_verified_wheel, main, single_source_archive

VERSION = source_project_version()


class SourceWheelBuilderTests(unittest.TestCase):
    def test_archive_selection_rejects_zero_or_multiple_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            with self.assertRaisesRegex(SuiteError, "one non-symlink"):
                single_source_archive(source)
            (source / "a.tar.gz").write_bytes(b"synthetic")
            (source / "b.tar.gz").write_bytes(b"synthetic")
            with self.assertRaisesRegex(SuiteError, "one non-symlink"):
                single_source_archive(source)

    def test_existing_wheel_directory_remains_untouched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "src"
            source.mkdir()
            (source / f"kira_agent_trace_lab-{VERSION}.tar.gz").write_bytes(b"synthetic")
            target = root / "wheel"
            target.mkdir()
            sentinel = target / "private_file"
            sentinel.write_bytes(b"DO_NOT_OVERWRITE")
            with patch("scripts.wheel_from_sdist.verify_sdist", return_value={"version": VERSION}):
                with patch("scripts.wheel_from_sdist.subprocess.run") as runner:
                    with self.assertRaisesRegex(SuiteError, "empty normal directory"):
                        build_verified_wheel(source, target)
                    runner.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"DO_NOT_OVERWRITE")

    def test_source_version_mismatch_rejected_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "src"
            source.mkdir()
            (source / f"kira_agent_trace_lab-{VERSION}.tar.gz").write_bytes(b"synthetic")
            with patch("scripts.wheel_from_sdist.verify_sdist", return_value={"version": "0.4.0"}):
                with patch("scripts.wheel_from_sdist.subprocess.run") as runner:
                    with self.assertRaisesRegex(SuiteError, "differs"):
                        build_verified_wheel(source, Path(temp) / "wheel")
                    runner.assert_not_called()

    def test_build_invokes_pip_only_on_source_verified_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "src"
            source.mkdir()
            tarball = source / f"kira_agent_trace_lab-{VERSION}.tar.gz"
            tarball.write_bytes(b"synthetic")
            target = root / "wheel"

            def fake_build(args, **kwargs):
                self.assertIn("--no-deps", args)
                self.assertEqual(args[-1], str(tarball))
                self.assertEqual(kwargs["cwd"].name, "kira-agent-trace-lab")
                (target / f"kira_agent_trace_lab-{VERSION}-py3-none-any.whl").write_bytes(b"synthetic")
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

            with patch("scripts.wheel_from_sdist.verify_sdist", return_value={"version": VERSION}) as validate:
                with patch("scripts.wheel_from_sdist.subprocess.run", side_effect=fake_build) as runner:
                    with patch("scripts.wheel_from_sdist.validate_release_metadata", return_value=VERSION):
                        with patch("scripts.wheel_from_sdist.wheel_members", return_value=set()):
                            result = build_verified_wheel(source, target)
            validate.assert_called_once_with(tarball)
            runner.assert_called_once()
            self.assertEqual(result["version"], VERSION)
            self.assertFalse(result["recorded_agent_actions_executed"])

    def test_cli_does_not_echo_private_paths_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "PRIVATE_TRACE_SOURCE_DO_NOT_ECHO"
            source.mkdir()
            output = StringIO()
            with redirect_stdout(output):
                code = main(["--sdist-dir", str(source),
                             "--wheel-dir", str(Path(temp) / "wheel")])
            self.assertEqual(code, 1)
            self.assertIn("NOT_VERIFIED", output.getvalue())
            self.assertNotIn("PRIVATE_TRACE_SOURCE_DO_NOT_ECHO", output.getvalue())


if __name__ == "__main__":
    unittest.main()
