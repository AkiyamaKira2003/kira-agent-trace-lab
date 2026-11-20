"""Build one wheel from a source-verified sdist without a version literal.

Source-checkout/CI helper only; not included in the installed package.
Never executes recorded agent actions. Does not emit pip build logs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from agent_trace_lab.schema import SuiteError
from scripts.verify_installed_wheel import (
    ROOT, source_project_version, validate_release_metadata, wheel_members,
)
from scripts.verify_source_sdist import verify_sdist


def single_source_archive(folder: Path) -> Path:
    """Require exactly one non-symlink archive in the supplied directory."""
    if not folder.is_dir() or folder.is_symlink():
        raise SuiteError("source archive directory missing or unsafe")
    archives = list(folder.glob("*.tar.gz"))
    if len(archives) != 1 or archives[0].is_symlink():
        raise SuiteError("expected one non-symlink source archive")
    return archives[0]


def build_verified_wheel(sdist_dir: Path, wheel_dir: Path) -> dict[str, object]:
    """Validate local source bytes before asking pip to build from that tar."""
    archive = single_source_archive(sdist_dir)
    verified = verify_sdist(archive)
    version = source_project_version()
    if verified["version"] != version:
        raise SuiteError("source archive version differs from checked-out source")
    if wheel_dir.is_symlink() or (
        wheel_dir.exists() and (not wheel_dir.is_dir() or any(wheel_dir.iterdir()))
    ):
        raise SuiteError("wheel output must be an empty normal directory")
    wheel_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps",
         "--wheel-dir", str(wheel_dir), str(archive)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        timeout=120, check=False,
    )
    if result.returncode:
        raise SuiteError("verified source archive wheel build failed")
    wheels = list(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise SuiteError("expected exactly one rebuilt wheel")
    if validate_release_metadata(wheels[0]) != version:
        raise SuiteError("rebuilt wheel metadata version mismatch")
    wheel_members(wheels[0])
    return {
        "status": "VERIFIED_SOURCE_ARCHIVE_WHEEL_BUILT",
        "version": version,
        "wheel_name": wheels[0].name,
        "recorded_agent_actions_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdist-dir", required=True, type=Path)
    parser.add_argument("--wheel-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build_verified_wheel(args.sdist_dir, args.wheel_dir), sort_keys=True))
    except (SuiteError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        # Errors and subprocess logs can include private local file names
        # and paths, so only expose a bounded exception category.
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
