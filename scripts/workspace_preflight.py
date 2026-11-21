"""Read-only workspace risk snapshot for KIRAA's autonomous coding campaign.

This is an operational tool, not part of the Agent Trace Lab evaluation API.
It neither locks worktrees nor proves absence of other sessions or file handles.
"""

from __future__ import annotations

import argparse
import json
import ntpath
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


_CIM_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($env:KIRA_PREFLIGHT_ROOT).TrimEnd('\') + '\'
$ids = @(Get-CimInstance Win32_Process |
  Where-Object { $_.ExecutablePath -and
    $_.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) } |
  ForEach-Object { [int]$_.ProcessId })
ConvertTo-Json -InputObject $ids -Compress
"""


def windows_path_inside(root: str, executable: str) -> bool:
    """Test directory containment without the unsafe string-prefix shortcut."""
    if not root or not executable or not ntpath.isabs(root) or not ntpath.isabs(executable):
        return False
    normalized_root = ntpath.normcase(ntpath.normpath(root))
    normalized_exe = ntpath.normcase(ntpath.normpath(executable))
    try:
        return ntpath.commonpath([normalized_root, normalized_exe]) == normalized_root
    except ValueError:
        return False


def matching_windows_pids(root: str, processes: Sequence[Mapping[str, Any]]) -> list[int]:
    """Return only process IDs, never command lines or executable paths."""
    result: set[int] = set()
    for process in processes:
        pid = process.get("ProcessId")
        executable = process.get("ExecutablePath")
        if type(pid) is int and pid > 0 and isinstance(executable, str):
            if windows_path_inside(root, executable):
                result.add(pid)
    return sorted(result)


def assess_risk(
    dirty_count: int,
    worktree_count: int,
    live_pids: Sequence[int],
    process_visibility: str,
) -> dict[str, Any]:
    """Avoid asserting safety from a one-time, incomplete observation."""
    reasons = []
    if dirty_count:
        reasons.append("dirty_worktree")
    if live_pids:
        reasons.append("running_executable_in_checkout")
    if reasons:
        verdict = "hold"
    elif process_visibility != "observed":
        verdict = "review"
        reasons = ["process_visibility_" + process_visibility]
    elif worktree_count > 1:
        verdict = "review"
        reasons = ["multiple_git_worktrees"]
    else:
        verdict = "no_observed_blocker"
    return {"verdict": verdict, "reasons": reasons}


def _git(root: Path, *args: str) -> str:
    # --no-optional-locks prevents Git status from refreshing the index as a
    # side effect. Disable custom fsmonitor hooks too; this is a read-only probe.
    result = subprocess.run(
        [
            "git", "--no-optional-locks", "-c", "core.fsmonitor=false",
            "-c", "core.untrackedCache=false", "-C", str(root), *args,
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=15, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError("git_read_failed")
    return result.stdout.strip()


def _scan_windows_processes(root: Path) -> tuple[list[int], str]:
    """Get process IDs from local CIM; a denied/incomplete probe is unknown."""
    if sys.platform != "win32":
        return [], "unsupported"
    env = os.environ.copy()
    env["KIRA_PREFLIGHT_ROOT"] = str(root)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _CIM_SCRIPT],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env, timeout=20, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return [], "unavailable"
        raw = json.loads(result.stdout)
        if not isinstance(raw, list):
            return [], "unavailable"
        if any(type(pid) is not int or pid < 1 for pid in raw):
            return [], "unavailable"
        return sorted(set(raw)), "observed"
    except (OSError, ValueError, subprocess.SubprocessError):
        return [], "unavailable"


def inspect_checkout(
    root: str | Path,
    *,
    process_snapshot: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Inspect one exact checkout, without changing its branch or index."""
    directory = Path(root).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("invalid_repository")
    actual_root = Path(_git(directory, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if actual_root != directory:
        raise ValueError("not_checkout_root")
    head = _git(directory, "rev-parse", "HEAD")
    branch = _git(directory, "branch", "--show-current") or "(detached)"
    dirty_count = len(_git(
        directory, "status", "--porcelain=v1", "--untracked-files=all",
    ).splitlines())
    worktree_count = sum(
        line.startswith("worktree ")
        for line in _git(directory, "worktree", "list", "--porcelain").splitlines()
    )
    if process_snapshot is None:
        live_pids, process_visibility = _scan_windows_processes(directory)
    else:
        live_pids = matching_windows_pids(str(directory), process_snapshot)
        process_visibility = "observed"
    risk = assess_risk(dirty_count, worktree_count, live_pids, process_visibility)
    return {
        "repo": directory.name,
        "head": head,
        "branch": branch,
        "dirty_count": dirty_count,
        "worktree_count": worktree_count,
        "live_process_count": len(live_pids),
        "live_pids": live_pids,
        "process_visibility": process_visibility,
        **risk,
        "limitation": (
            "This snapshot cannot detect browser/agent sessions, working directories, "
            "DLL locks, all protected processes, or races after the scan."
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only coding checkout preflight")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        result = inspect_checkout(args.repo)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        result = {"verdict": "error", "error_code": "checkout_probe_failed"}
        code = 2
    else:
        code = 0 if result["verdict"] == "no_observed_blocker" else 3
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
