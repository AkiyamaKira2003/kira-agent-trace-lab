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


def _execute(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    completed = subprocess.run(
        args, cwd=str(cwd), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=45, check=False,
    )
    if completed.returncode:
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
    return {
        "status": "ISOLATED_INSTALLED_WHEEL_SMOKE_PASS",
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "wheel_members_checked": len(names),
        "synthetic_dojo_calls_imported_not_executed": 2,
        "synthetic_policy_cases_matched": 8,
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
