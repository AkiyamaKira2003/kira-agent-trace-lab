"""Offline, isolated installed-wheel smoke for the published package boundary.

Consumes one locally built wheel and self-authored synthetic examples. The
research-only scripts/ and metadata audits remain in the source repository,
not in the wheel. No tool calls from any recorded trace are executed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import zipfile

from agent_trace_lab.schema import SuiteError

ROOT = Path(__file__).resolve().parents[1]
WHEEL_MAX_SIZE = 2 * 1024 * 1024
EXAMPLES = (
    "suite.json",
    "agentdojo_recorded_synthetic.json",
    "agentdojo_policy_simulated_scope.json",
    "demo_permissive.json",
    "demo_task_scoped.json",
)
REQUIRED_WHEEL_MEMBERS = frozenset({
    "agent_trace_lab/__init__.py",
    "agent_trace_lab/__main__.py",
    "agent_trace_lab/cli.py",
    "agent_trace_lab/agentdojo.py",
    "agent_trace_lab/engine.py",
    "agent_trace_lab/schema.py",
})


def wheel_members(path: Path) -> set[str]:
    if (not path.is_file() or not path.name.startswith("kira_agent_trace_lab-")
            or path.suffix != ".whl" or not 0 < path.stat().st_size <= WHEEL_MAX_SIZE):
        raise SuiteError("wheel path or size is not a verified local package candidate")
    try:
        with zipfile.ZipFile(path) as bundle:
            members = bundle.namelist()
    except zipfile.BadZipFile as exc:
        raise SuiteError("not a valid wheel archive") from exc
    if (len(members) != len(set(members))
            or any(chr(92) in member or member.startswith("/") or ".." in member.split("/")
                   for member in members)):
        raise SuiteError("unsafe or duplicated wheel archive member")
    names = set(members)
    if not REQUIRED_WHEEL_MEMBERS <= names:
        raise SuiteError("installed CLI code or AgentDojo importer missing from wheel")
    if any(member.startswith(("scripts/", "docs/", "artifacts/", "examples/"))
           or member.endswith((".pyc", ".env")) for member in names):
        raise SuiteError("source-only scripts, local artifacts or secrets bundled into wheel")
    return names


def validate_evaluation(data: Any, total: int) -> None:
    if not isinstance(data, dict) or not isinstance(data.get("summary"), dict):
        raise SuiteError("isolated evaluator did not return a JSON summary")
    summary = data["summary"]
    if type(summary.get("total")) is not int or type(summary.get("matched")) is not int:
        raise SuiteError("isolated evaluator summary has wrong types")
    if summary["total"] != total or summary["matched"] != total:
        raise SuiteError("isolated synthetic fixture verdicts changed")


def validate_policy_contrast(permissive: Any, task_scoped: Any) -> None:
    """Validate exact synthetic outcomes, never assert real permission accuracy."""
    if not isinstance(permissive, dict) or permissive.get("schema_version") != "1.0":
        raise SuiteError("permissive demo returned invalid schema")
    summary = permissive.get("summary")
    cases = permissive.get("cases")
    if (not isinstance(summary, dict) or summary.get("total") != 1
            or summary.get("matched") != 0 or not isinstance(cases, list)
            or len(cases) != 1 or not isinstance(cases[0], dict)):
        raise SuiteError("permissive demo must expose exactly one labeled mismatch")
    broad = cases[0]
    if (broad.get("id") != "unrequested_forward" or broad.get("expected") != "deny"
            or broad.get("actual") != "allow" or broad.get("matched") is not False
            or broad.get("violations") != []):
        raise SuiteError("permissive demo no longer exposes the intended tool-name gap")
    if not isinstance(task_scoped, dict) or task_scoped.get("schema_version") != "1.1":
        raise SuiteError("task-scoped demo returned invalid schema")
    validate_evaluation(task_scoped, 5)
    rows = task_scoped.get("cases")
    expected = {
        "unrequested_forward": ("deny", "TASK_GRANT_REQUIRED", 0),
        "approved_forward": ("allow", None, None),
        "redirected_recipient": ("deny", "TASK_GRANT_REQUIRED", 0),
        "replayed_single_grant": ("deny", "TASK_GRANT_REQUIRED", 1),
        "ordinary_inbox_search": ("allow", None, None),
    }
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise SuiteError("task-scoped demo missing cases")
    if [row.get("id") for row in rows if isinstance(row, dict)] != list(expected):
        raise SuiteError("task-scoped demo case identities or order changed")
    for row in rows:
        if not isinstance(row, dict):
            raise SuiteError("task-scoped demo case is not an object")
        actual, code, event_index = expected[row["id"]]
        if (row.get("actual") != actual or row.get("expected") != actual
                or row.get("matched") is not True):
            raise SuiteError("task-scoped demo outcome changed")
        violations = row.get("violations")
        if code is None:
            if violations != []:
                raise SuiteError("approved/ordinary action unexpectedly rejected")
        elif (not isinstance(violations, list) or len(violations) != 1
              or not isinstance(violations[0], dict)
              or violations[0].get("code") != code
              or violations[0].get("event_index") != event_index
              or violations[0].get("tool") != "forward_email"):
            raise SuiteError("task-scoped denial reason or action index changed")


def _execute(args: list[str], cwd: Path, env: dict[str, str], *, expected_exit: int = 0) -> str:
    completed = subprocess.run(
        args, cwd=str(cwd), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=45, check=False,
    )
    if completed.returncode != expected_exit:
        # Do not forward path-rich, potentially sensitive CLI error output.
        raise SuiteError("isolated package subprocess returned failure")
    return completed.stdout


def run(wheel: Path) -> dict[str, Any]:
    wheel = wheel.resolve()
    names = wheel_members(wheel)
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wheel-qa-", dir=artifacts) as directory:
        base = Path(directory)
        site = base / "installed_site"
        work = base / "outside_source"
        site.mkdir()
        work.mkdir()
        for name in EXAMPLES:
            shutil.copyfile(ROOT / "examples" / name, work / name)
        # --no-index and --no-deps prohibit fetching dependencies or extras.
        _execute([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
                  "--target", str(site), str(wheel)], work, os.environ.copy())
        env = os.environ.copy()
        env["PYTHONPATH"] = str(site)
        env["PYTHONNOUSERSITE"] = "1"
        # -S disables site initialization; workdir contains only synthetic
        # fixture copies. Any success therefore comes from installed_site.
        installed_path = _execute(
            [sys.executable, "-S", "-c", "import agent_trace_lab; print(agent_trace_lab.__file__)"],
            work, env,
        ).strip()
        if not Path(installed_path).resolve().is_relative_to(site.resolve()):
            raise SuiteError("smoke imported source checkout instead of installed wheel")
        _execute([
            sys.executable, "-S", "-m", "agent_trace_lab", "import-agentdojo",
            "agentdojo_recorded_synthetic.json", "--policy-suite",
            "agentdojo_policy_simulated_scope.json", "--case-id", "wheel_synthetic",
            "--expected", "allow", "--output", "imported.json",
        ], work, env)
        imported = json.loads((work / "imported.json").read_text(encoding="utf-8"))
        if (len(imported["cases"]) != 1 or len(imported["cases"][0]["trace"]) != 2
                or imported["cases"][0]["expected"] != "allow"):
            raise SuiteError("installed AgentDojo import did not preserve synthetic actions")
        validate_evaluation(json.loads(_execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", "evaluate",
             "imported.json", "--format", "json"], work, env)), 1)
        validate_evaluation(json.loads(_execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", "evaluate",
             "suite.json", "--format", "json"], work, env)), 8)
        # Deliberate mismatch on permissive schema 1.0 MUST exit 1. A
        # missing task grant on schema 1.1 must deny without executing calls.
        permissive = json.loads(_execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", "evaluate",
             "demo_permissive.json", "--format", "json"], work, env, expected_exit=1))
        scoped = json.loads(_execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", "evaluate",
             "demo_task_scoped.json", "--format", "json"], work, env))
        validate_policy_contrast(permissive, scoped)
    return {
        "status": "ISOLATED_INSTALLED_WHEEL_SMOKE_PASS",
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "wheel_members_checked": len(names),
        "synthetic_dojo_calls_imported_not_executed": 2,
        "synthetic_policy_cases_matched": 8,
        "synthetic_permissive_expected_mismatch": True,
        "synthetic_task_scoped_cases_matched": 5,
        "synthetic_task_scoped_real_grants_authenticated": False,
        "isolated_site_import_verified": True,
        "research_scripts_shipped_in_wheel": False,
        "authenticated_user_grants_verified": False,
        "agent_safety_accuracy_claimed": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", required=True, type=Path,
                        help="directory containing exactly one locally built project wheel")
    args = parser.parse_args()
    try:
        wheels = list(args.wheel_dir.glob("kira_agent_trace_lab-*.whl"))
        if len(wheels) != 1:
            raise SuiteError("expected exactly one local project wheel")
        print(json.dumps(run(wheels[0]), sort_keys=True))
    except (OSError, ValueError, UnicodeError, RecursionError, TimeoutError,
            subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
