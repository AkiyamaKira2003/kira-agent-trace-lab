"""Compare two same-revision, source-date-pinned development wheel builds.

This is a within-environment reproducibility test, NOT a cross-platform
byte-for-byte claim, security audit, or validation of real agent permissions.
Only hashes, sizes and bounded status metadata reach stdout.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

from agent_trace_lab.schema import SuiteError
from scripts.verify_installed_wheel import ROOT, wheel_members

EXPECTED_WHEEL_NAME = "kira_agent_trace_lab-0.5.0.dev0-py3-none-any.whl"
EPOCH_RE = re.compile(r"[0-9]{9,12}\Z")


def validate_epoch(value: Any) -> str:
    """Fail closed on invalid timestamps and pre-1980 ZIP epoch values."""
    if not isinstance(value, str) or EPOCH_RE.fullmatch(value) is None:
        raise SuiteError("SOURCE_DATE_EPOCH is not a bounded decimal timestamp")
    stamp = int(value)
    if not 315532800 <= stamp <= 4102444800:  # 1980-01-01 through 2100-01-01 UTC
        raise SuiteError("SOURCE_DATE_EPOCH outside supported wheel ZIP timestamp range")
    return value


def get_git_commit_epoch() -> str:
    process = subprocess.run(
        ["git", "show", "-s", "--format=%ct", "HEAD"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", timeout=15, check=False,
    )
    if process.returncode:
        raise SuiteError("pinned Git commit timestamp unavailable")
    return validate_epoch(process.stdout.strip())


def compare_wheels(first: Path, second: Path) -> dict[str, Any]:
    if first.name != EXPECTED_WHEEL_NAME or second.name != EXPECTED_WHEEL_NAME:
        raise SuiteError("unexpected wheel name or package version")
    members_first = wheel_members(first)
    members_second = wheel_members(second)
    if members_first != members_second:
        raise SuiteError("wheel package member sets differ")
    first_hash = hashlib.sha256(first.read_bytes()).hexdigest()
    second_hash = hashlib.sha256(second.read_bytes()).hexdigest()
    if first_hash != second_hash:
        raise SuiteError("two builds differ despite a pinned SOURCE_DATE_EPOCH")
    return {
        "status": "WITHIN_ENVIRONMENT_BYTE_IDENTICAL_WHEELS",
        "wheel_sha256": first_hash,
        "wheel_member_count": len(members_first),
        "bytes_compared": first.stat().st_size,
        "cross_platform_byte_identity_claimed": False,
        "authenticated_human_authorization_verified": False,
        "recorded_agent_actions_executed": False,
    }


def build_twice() -> dict[str, Any]:
    stamp = get_git_commit_epoch()
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = stamp
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    ignore = ROOT / "artifacts"
    ignore.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wheel-repro-", dir=ignore) as tmp:
        root = Path(tmp)
        wheels = []
        for label in ("first", "second"):
            dest = root / label
            dest.mkdir()
            result = subprocess.run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps",
                 "--wheel-dir", str(dest), str(ROOT)],
                cwd=str(ROOT), env=env, capture_output=True,
                text=True, encoding="utf-8", timeout=120, check=False,
            )
            if result.returncode:
                # Avoid leaking paths/log output, which can include private
                # data on developer machines.
                raise SuiteError("isolated wheel build subprocess returned failure")
            entries = list(dest.glob("*.whl"))
            if len(entries) != 1:
                raise SuiteError("expected exactly one wheel per build")
            wheels.append(entries[0])
        evidence = compare_wheels(*wheels)
        evidence["source_date_epoch"] = stamp
    return evidence


def main() -> int:
    try:
        print(json.dumps(build_twice(), sort_keys=True))
    except (OSError, ValueError, UnicodeError, RecursionError,
            subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
