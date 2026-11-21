"""Source-only smoke and negative tests for the campaign workspace guard."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.workspace_preflight import (
    _scan_windows_processes,
    assess_risk,
    inspect_checkout,
    main,
    matching_windows_pids,
    windows_path_inside,
)


class WorkspacePreflightTests(unittest.TestCase):
    def test_windows_boundary_is_case_insensitive_but_not_prefix_based(self):
        root = r"C:\Projects\PiPClickThrough"
        self.assertTrue(windows_path_inside(root, r"c:\PROJECTS\pipclickthrough\Release\app.exe"))
        self.assertFalse(windows_path_inside(root, r"C:\Projects\PiPClickThrough-backup\app.exe"))
        self.assertFalse(windows_path_inside(root, r"C:\Projects\AnotherRepo\app.exe"))
        self.assertFalse(windows_path_inside(root, r"D:\Projects\PiPClickThrough\app.exe"))
        self.assertFalse(windows_path_inside(root, r".\Release\app.exe"))
        self.assertFalse(windows_path_inside(root, ""))

    def test_windows_process_filter_never_exposes_unrelated_paths(self):
        root = r"C:\Projects\PiPClickThrough"
        processes = [
            {"ProcessId": 22, "ExecutablePath": r"c:\Projects\PiPClickThrough\bin\test.exe"},
            {"ProcessId": 11, "ExecutablePath": r"C:\Projects\PiPClickThrough\app.exe"},
            {"ProcessId": 44, "ExecutablePath": r"C:\Projects\PiPClickThrough2\app.exe"},
            {"ProcessId": 33, "ExecutablePath": r"C:\Windows\System32\cmd.exe"},
            {"ProcessId": 55, "ExecutablePath": None},
            {"ProcessId": "bad", "ExecutablePath": r"C:\Projects\PiPClickThrough\bad.exe"},
        ]
        self.assertEqual(matching_windows_pids(root, processes), [11, 22])

    def test_escaped_windows_paths_do_not_count_as_checkout_processes(self):
        root = r"C:\Projects\PiPClickThrough"
        self.assertFalse(windows_path_inside(root, r"C:\Projects\PiPClickThrough\..\Other\bad.exe"))
        self.assertFalse(windows_path_inside(root, r"C:\Projects\PiPClickThrough.evil\bad.exe"))

    def test_windows_process_scan_failure_is_unverified_not_clear(self):
        with patch("scripts.workspace_preflight.sys.platform", "win32"), patch(
            "scripts.workspace_preflight.subprocess.run", side_effect=OSError("private error")
        ):
            pids, visibility = _scan_windows_processes(Path(r"C:\Projects\PiPClickThrough"))
        self.assertEqual(pids, [])
        self.assertEqual(visibility, "unavailable")

    def test_preflight_fails_closed_on_dirty_or_live_process(self):
        self.assertEqual(assess_risk(1, 1, [], "observed")["verdict"], "hold")
        self.assertEqual(assess_risk(0, 1, [34140], "observed")["verdict"], "hold")
        self.assertEqual(assess_risk(3, 1, [34140], "observed")["reasons"],
                         ["dirty_worktree", "running_executable_in_checkout"])

    def test_unknown_process_visibility_never_claims_safe(self):
        self.assertEqual(assess_risk(0, 1, [], "unavailable")["verdict"], "review")
        self.assertEqual(assess_risk(0, 1, [], "unsupported")["verdict"], "review")
        self.assertEqual(assess_risk(0, 2, [], "observed")["verdict"], "review")
        clear = assess_risk(0, 1, [], "observed")
        self.assertEqual(clear["verdict"], "no_observed_blocker")
        self.assertNotIn("safe", json.dumps(clear))

    def test_git_integration_reads_snapshot_and_does_not_mutate_checkout(self):
        with tempfile.TemporaryDirectory(prefix="workspace-preflight-test-") as temp:
            root = Path(temp)
            def git(*args: str) -> str:
                result = subprocess.run(
                    ["git", "-C", str(root), *args],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=10,
                )
                return result.stdout.strip()

            git("init", "-q")
            (root / "tracked.txt").write_text("synthetic-v1", encoding="utf-8")
            git("add", "tracked.txt")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "-c", "commit.gpgsign=false",
                "commit", "-qm", "synthetic fixture")
            original_head = git("rev-parse", "HEAD")
            clean = inspect_checkout(root, process_snapshot=[])
            self.assertEqual(clean["head"], original_head)
            self.assertEqual(clean["dirty_count"], 0)
            self.assertEqual(clean["worktree_count"], 1)
            self.assertEqual(clean["process_visibility"], "observed")
            self.assertEqual(clean["verdict"], "no_observed_blocker")
            (root / "tracked.txt").write_text("synthetic-v2", encoding="utf-8")
            dirty = inspect_checkout(root, process_snapshot=[])
            self.assertEqual(dirty["dirty_count"], 1)
            self.assertEqual(dirty["verdict"], "hold")
            self.assertEqual(git("rev-parse", "HEAD"), original_head)
            self.assertEqual((root / "tracked.txt").read_text("utf-8"), "synthetic-v2")

    def test_cli_reports_only_metadata_and_exits_nonzero_for_dirty(self):
        with tempfile.TemporaryDirectory(prefix="workspace-preflight-test-") as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=10)
            (root / "tracked.txt").write_text("synthetic", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True, timeout=10)
            subprocess.run([
                "git", "-C", str(root), "-c", "user.name=Test",
                "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
                "commit", "-qm", "synthetic fixture",
            ], check=True, timeout=10)
            (root / "secret_filename.txt").write_text("SENSITIVE_SENTINEL_9021", encoding="utf-8")
            with patch("scripts.workspace_preflight._scan_windows_processes",
                       return_value=([], "observed")):
                output = StringIO()
                with redirect_stdout(output):
                    exit_code = main(["--repo", str(root)])
            self.assertEqual(exit_code, 3)
            report = json.loads(output.getvalue())
            self.assertEqual(report["verdict"], "hold")
            self.assertEqual(report["dirty_count"], 1)
            self.assertNotIn("secret_filename", output.getvalue())
            self.assertNotIn("SENSITIVE_SENTINEL", output.getvalue())

    def test_invalid_repository_returns_machine_readable_error(self):
        with tempfile.TemporaryDirectory(prefix="workspace-preflight-test-") as temp:
            out = StringIO()
            with redirect_stdout(out):
                code = main(["--repo", temp])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out.getvalue())["verdict"], "error")

    def test_subdirectory_of_a_git_checkout_is_rejected_as_a_root(self):
        with tempfile.TemporaryDirectory(prefix="workspace-preflight-test-") as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=10)
            nested = root / "nested"
            nested.mkdir()
            with self.assertRaisesRegex(ValueError, "not_checkout_root"):
                inspect_checkout(nested, process_snapshot=[])


if __name__ == "__main__":
    unittest.main()
