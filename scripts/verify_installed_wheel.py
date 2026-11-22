"""Offline, isolated installed-wheel smoke for the published package boundary.

Consumes one locally built wheel and self-authored synthetic examples. The
research-only scripts/ and metadata audits remain in the source repository,
not in the wheel. No tool calls from any recorded trace are executed.
"""

from __future__ import annotations

import hashlib
from email.parser import BytesParser
from email.policy import default as email_policy
import json
import os
from pathlib import Path
import re
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
    "otlp_spans.json",
    "otlp_audit_policy.json",
    "swe_recorded_row_synthetic.json",
    "swe_structural_policy.json",
    "responses_function_calls_synthetic.json",
    "responses_sequence_synthetic.json",
    "agentdojo_recorded_synthetic.json",
    "agentdojo_policy_simulated_scope.json",
    "demo_permissive.json",
    "demo_task_scoped.json",
    "compare_candidate_task_guarded.json",
)
REQUIRED_WHEEL_MEMBERS = frozenset({
    "agent_trace_lab/__init__.py",
    "agent_trace_lab/__main__.py",
    "agent_trace_lab/cli.py",
    "agent_trace_lab/agentdojo.py",
    "agent_trace_lab/responses.py",
    "agent_trace_lab/engine.py",
    "agent_trace_lab/schema.py",
})

WHEEL_FILENAME = re.compile(
    r"^kira_agent_trace_lab-(?P<version>[0-9][0-9A-Za-z.!+_-]*)-py3-none-any\.whl$"
)
RELEASE_LINKS = frozenset({
    "Homepage": "https://github.com/AkiyamaKira2003/kira-agent-trace-lab",
    "Repository": "https://github.com/AkiyamaKira2003/kira-agent-trace-lab",
    "Issues": "https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues",
    "Documentation": "https://github.com/AkiyamaKira2003/kira-agent-trace-lab/blob/main/README.md",
}.items())


def source_project_version() -> str:
    """Read one literal project version using stdlib on Python 3.10+."""
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = re.search(r"(?ms)^\[project\]\s*\r?\n(.*?)(?=^\[|\Z)", source)
    if section is None:
        raise SuiteError("project metadata section is missing")
    versions = re.findall(
        r'^version\s*=\s*"([0-9][0-9A-Za-z.!+_-]*)"\s*$',
        section.group(1), flags=re.MULTILINE,
    )
    if len(versions) != 1:
        raise SuiteError("source project version is absent or ambiguous")
    return versions[0]


def validate_release_metadata(path: Path) -> str:
    """Inspect the actual distributable's release/legal/CLI declarations."""
    filename = WHEEL_FILENAME.fullmatch(path.name)
    if filename is None:
        raise SuiteError("wheel filename is not the expected pure-Python distribution")
    version = filename.group("version")
    if version != source_project_version():
        raise SuiteError("wheel release version differs from checked-out source")
    prefix = f"kira_agent_trace_lab-{version}.dist-info/"
    try:
        with zipfile.ZipFile(path) as bundle:
            metadata = BytesParser(policy=email_policy).parsebytes(
                bundle.read(prefix + "METADATA")
            )
            entrypoints = bundle.read(prefix + "entry_points.txt").decode("utf-8")
            wheel = bundle.read(prefix + "WHEEL").decode("utf-8")
            license_text = bundle.read(prefix + "licenses/LICENSE").decode("utf-8")
    except (KeyError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        raise SuiteError("wheel release metadata or license document missing") from exc

    urls = set()
    for item in metadata.get_all("Project-URL", []):
        if ", " not in item:
            raise SuiteError("malformed wheel project URL metadata")
        label, url = item.split(", ", 1)
        urls.add((label, url))
    if (metadata.get("Name") != "kira-agent-trace-lab"
            or metadata.get("Version") != version
            or metadata.get("License-Expression") != "MIT"
            or metadata.get("Requires-Python") != ">=3.10"
            or metadata.get_all("Requires-Dist")
            or "LICENSE" not in metadata.get_all("License-File", [])
            or not RELEASE_LINKS <= urls):
        raise SuiteError("wheel package/release declarations failed verification")
    if (entrypoints.strip() !=
            "[console_scripts]\nagent-trace-lab = agent_trace_lab.cli:main"
            or "Tag: py3-none-any" not in wheel
            or "MIT License" not in license_text
            or "Permission is hereby granted" not in license_text):
        raise SuiteError("wheel entry point, platform tag or embedded license inconsistent")
    return version


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


def installed_console_path(site: Path, platform_name: str) -> Path:
    """Find the pip --target console launcher without assuming Scripts on Windows."""
    if platform_name not in ("nt", "posix"):
        raise SuiteError("unsupported console launcher platform")
    name = "agent-trace-lab.exe" if platform_name == "nt" else "agent-trace-lab"
    launcher = site / "bin" / name
    if (not launcher.is_file()
            or not launcher.resolve().is_relative_to(site.resolve())
            or (platform_name == "posix" and not os.access(launcher, os.X_OK))):
        raise SuiteError("installed wheel console launcher absent or unsafe")
    return launcher


def validate_console_equivalence(module_permissive: Any, module_scoped: Any,
                                 console_permissive: Any, console_scoped: Any) -> None:
    validate_policy_contrast(module_permissive, module_scoped)
    validate_policy_contrast(console_permissive, console_scoped)
    if console_permissive != module_permissive or console_scoped != module_scoped:
        raise SuiteError("installed console launcher differs from module CLI")


def _execute(args: list[str], cwd: Path, env: dict[str, str], *, expected_exit: int = 0) -> str:
    completed = subprocess.run(
        args, cwd=str(cwd), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=45, check=False,
    )
    if completed.returncode != expected_exit:
        # Do not forward path-rich, potentially sensitive CLI error output.
        raise SuiteError("isolated package subprocess returned failure")
    return completed.stdout


def verify_installed_diagnostic(args: list[str], cwd: Path,
                                env: dict[str, str], private_marker: str) -> None:
    """Check expected malformed-input rejection without emitting raw stderr."""
    completed = subprocess.run(
        args, cwd=str(cwd), env=env, capture_output=True, text=True,
        encoding="utf-8", timeout=45, check=False,
    )
    if (completed.returncode != 2
            or private_marker in completed.stderr
            or private_marker in completed.stdout
            or "unexpected_count=1" not in completed.stderr):
        raise SuiteError("installed malformed-input diagnostic redaction failed")


def verify_installed_io_diagnostic(
    args: list[str], cwd: Path, env: dict[str, str],
    private_marker: str, category: str,
) -> None:
    """Check bounded installed I/O errors without forwarding raw stderr."""
    completed = subprocess.run(
        args, cwd=str(cwd), env=env, capture_output=True,
        text=True, encoding="utf-8", timeout=45, check=False,
    )
    if (completed.returncode != 2
            or private_marker in completed.stdout + completed.stderr
            or category not in completed.stderr):
        raise SuiteError("installed I/O diagnostic privacy or category verification failed")


def validate_import_output_contract(before: bytes, after_block: bytes,
                                    after_explicit: bytes, old_id: str,
                                    new_id: str) -> None:
    """Check the installed CLI preserved existing bytes before opt-in replacement."""
    if before != after_block:
        raise SuiteError("installed importer silently replaced an existing file")
    if after_explicit == before or after_explicit == after_block:
        raise SuiteError("installed importer explicit overwrite did not replace output")
    try:
        first = json.loads(before)
        final = json.loads(after_explicit)
    except (UnicodeError, ValueError) as exc:
        raise SuiteError("installed importer output was not valid JSON") from exc
    original_cases = first.get("cases") if isinstance(first, dict) else None
    updated_cases = final.get("cases") if isinstance(final, dict) else None
    if (not isinstance(original_cases, list) or not isinstance(updated_cases, list)
            or len(original_cases) != 1 or len(updated_cases) != 1
            or not isinstance(original_cases[0], dict)
            or not isinstance(updated_cases[0], dict)
            or original_cases[0].get("id") != old_id
            or updated_cases[0].get("id") != new_id
            or original_cases[0].get("trace") != updated_cases[0].get("trace")):
        raise SuiteError("installed importer output contents changed beyond the case ID")


def run(wheel: Path) -> dict[str, Any]:
    wheel = wheel.resolve()
    names = wheel_members(wheel)
    release_version = validate_release_metadata(wheel)
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
        launcher = installed_console_path(site, os.name)
        # New unlabeled audit is read-only, shares the original OTLP parser
        # and action scanner, and must work from the installed distribution.
        audit_args = [
            "audit-otlp", "otlp_spans.json", "--policy-file",
            "otlp_audit_policy.json",
        ]
        module_audit = _execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", *audit_args],
            work, env,
        )
        console_audit = _execute([str(launcher), *audit_args], work, env)
        audited = json.loads(module_audit)
        if (module_audit != console_audit
                or audited["actual"] != "allow"
                or audited["recorded_action_count"] != 2
                or audited["violations"] != []
                or any(audited[key] is not False for key in (
                    "ground_truth_available", "user_authorization_verified",
                    "security_metrics_available", "trace_completeness_verified",
                    "recorded_actions_executed",
                ))
                or any(field in module_audit for field in (
                    '"expected"', '"confusion"', '"accuracy"',
                    '"arguments"', '"tool"', "files.read", "docs.search",
                ))):
            raise SuiteError("installed OTLP policy-only audit invented labels or leaked tool data")
        installed_audit_text = _execute(
            [str(launcher), *audit_args, "--format", "text"], work, env,
        )
        if "unverified" not in installed_audit_text or "allow" not in installed_audit_text:
            raise SuiteError("installed audit text omitted provenance limitations")
        # The CI gate must be explicit and preserve the same printed verdict.
        # Use only an installed synthetic policy copy, not any real trace.
        denial_policy = json.loads((work / "otlp_audit_policy.json").read_text(encoding="utf-8"))
        denial_policy["policy"]["max_actions"] = 1
        (work / "otlp_ci_denial_policy.json").write_text(
            json.dumps(denial_policy), encoding="utf-8",
        )
        denied_args = [
            "audit-otlp", "otlp_spans.json",
            "--policy-file", "otlp_ci_denial_policy.json",
        ]
        report_only = _execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", *denied_args],
            work, env,
        )
        gated = _execute(
            [str(launcher), *denied_args, "--fail-on-deny"],
            work, env, expected_exit=1,
        )
        module_gated = _execute(
            [sys.executable, "-S", "-m", "agent_trace_lab",
             *denied_args, "--fail-on-deny"],
            work, env, expected_exit=1,
        )
        allow_gated = _execute(
            [str(launcher), *audit_args, "--fail-on-deny"],
            work, env,
        )
        invalid_gated = _execute(
            [str(launcher), "audit-otlp", "missing.json",
             "--policy-file", "otlp_ci_denial_policy.json",
             "--fail-on-deny"], work, env, expected_exit=2,
        )
        if (report_only != gated or report_only != module_gated
                or module_audit != allow_gated
                or json.loads(gated)["actual"] != "deny"
                or any(key in gated for key in (
                    '"expected"', '"accuracy"', '"confusion"',
                    '"arguments"', "files.read", "docs.search",
                ))
                or invalid_gated):
            raise SuiteError("installed opt-in policy CI exit gate broke report parity")
        # Structural preflight is intentionally independent of policy
        # evaluation and caller labels, and serializes no case/tool values.
        validate_args = ["validate", "suite.json", "--format", "json"]
        module_preflight = _execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", *validate_args],
            work, env,
        )
        console_preflight = _execute(
            [str(launcher), *validate_args], work, env,
        )
        expected_keys = {
            "schema_version", "case_count", "recorded_call_count",
            "policy_tool_count", "guarded_tool_count", "evaluation_performed",
        }
        structural = json.loads(module_preflight)
        if (console_preflight != module_preflight
                or set(structural) != expected_keys
                or structural["schema_version"] != "1.0"
                or structural["case_count"] != 8
                or structural["policy_tool_count"] != 3
                or structural["evaluation_performed"] is not False
                or any(name in module_preflight for name in (
                    "normal_search", "files.read", "normal_file",
                    "TASK_GRANT_REQUIRED", "PRIVATE_SYNTHETIC"))):
            raise SuiteError("installed structural validation unexpectedly evaluated or leaked input")
        guarded_structural = json.loads(_execute(
            [str(launcher), "validate", "demo_task_scoped.json", "--format", "json"],
            work, env,
        ))
        if (guarded_structural["schema_version"] != "1.1"
                or guarded_structural["guarded_tool_count"] < 1
                or guarded_structural["evaluation_performed"] is not False):
            raise SuiteError("installed structural validation of guarded suite failed")
        destination = "installed_structural_counts.json"
        stored_args = [*validate_args, "--output", destination]
        if _execute([str(launcher), *stored_args], work, env):
            raise SuiteError("installed structural file output unexpectedly printed input data")
        if (work / destination).read_text(encoding="utf-8") != module_preflight:
            raise SuiteError("installed structural saved counts differ from stdout")
        _execute([str(launcher), *stored_args], work, env, expected_exit=2)
        _execute([str(launcher), *stored_args, "--overwrite"], work, env)
        if (work / destination).read_text(encoding="utf-8") != module_preflight:
            raise SuiteError("installed structural overwrite changed validated counts")
        input_bytes = (work / "suite.json").read_bytes()
        _execute(
            [str(launcher), *validate_args, "--output", "suite.json", "--overwrite"],
            work, env, expected_exit=2,
        )
        if ((work / "suite.json").read_bytes() != input_bytes
                or list(work.glob(".agent-trace-validate-*.tmp"))):
            raise SuiteError("installed structural validation modified original data")
        # Test all installed import commands, independently of
        # source-checkout imports. Two no-clobber invocations must preserve
        # the exact bytes and an explicit overwrite must change only case_id.
        import_cases = (
            ("otlp", "otlp_spans.json", "suite.json"),
            ("swe", "swe_recorded_row_synthetic.json", "swe_structural_policy.json"),
            ("agentdojo", "agentdojo_recorded_synthetic.json",
             "agentdojo_policy_simulated_scope.json"),
            ("responses", "responses_function_calls_synthetic.json", "suite.json"),
            ("responses-sequence", "responses_sequence_synthetic.json", "suite.json"),
        )
        untouched = work / "unrelated_private_sentinel.txt"
        sentinel = b"UNRELATED_SYNTHETIC_PRIVATE_FILE_DO_NOT_REPLACE"
        untouched.write_bytes(sentinel)
        for kind, recorded, policy in import_cases:
            output = f"installed_{kind}.json"
            source_id = f"installed_{kind}_original"
            updated_id = f"installed_{kind}_updated"
            common = [
                f"import-{kind}", recorded, "--policy-suite", policy,
                "--case-id", source_id, "--expected", "allow", "--output", output,
            ]
            module = [sys.executable, "-S", "-m", "agent_trace_lab"]
            _execute([*module, *common], work, env)
            original = (work / output).read_bytes()
            if kind == "responses-sequence":
                parsed = json.loads(original)
                if parsed["cases"][0]["trace"] != [
                    {"tool": "docs.search", "arguments": {"query": "README"}},
                    {"tool": "files.read", "arguments": {"path": "/workspace/docs/guide.md"}},
                ]:
                    raise SuiteError("installed response sequence lost call order")
            _execute([*module, *common], work, env, expected_exit=2)
            _execute([str(launcher), *common], work, env, expected_exit=2)
            blocked = (work / output).read_bytes()
            updated = common.copy()
            updated[updated.index(source_id)] = updated_id
            _execute([str(launcher), *updated, "--overwrite"], work, env)
            validate_import_output_contract(
                original, blocked, (work / output).read_bytes(), source_id, updated_id,
            )
            if (untouched.read_bytes() != sentinel
                    or list(work.glob(".agent-trace-import-*.tmp"))):
                raise SuiteError("installed importer modified unrelated data or left temp files")
        console_permissive = json.loads(_execute(
            [str(launcher), "evaluate", "demo_permissive.json", "--format", "json"],
            work, env, expected_exit=1))
        console_scoped = json.loads(_execute(
            [str(launcher), "evaluate", "demo_task_scoped.json", "--format", "json"],
            work, env))
        validate_console_equivalence(permissive, scoped, console_permissive, console_scoped)
        # Aggregate-only reports must not include identifying case/tool data
        # or mislabel caller-authored fixtures as independently verified.
        aggregate_args = [
            "evaluate", "suite.json", "--summary-only", "--format", "json",
        ]
        module_aggregate = json.loads(_execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", *aggregate_args],
            work, env,
        ))
        console_aggregate = json.loads(_execute(
            [str(launcher), *aggregate_args], work, env,
        ))
        aggregate_text = _execute(
            [str(launcher), "evaluate", "suite.json", "--summary-only",
             "--format", "text"], work, env,
        )
        if (module_aggregate != console_aggregate
                or module_aggregate["label_basis"] != "caller_supplied_not_independently_verified"
                or module_aggregate["verified_real_world_security_metrics"] is not False
                or module_aggregate["summary"]["total_cases"] != 8
                or module_aggregate["summary"]["matched_fixture_labels"] != 8
                or any(name in module_aggregate for name in ("cases", "policy"))
                or "accuracy" in json.dumps(module_aggregate)
                or "No independently verified real-world security metrics." not in aggregate_text
                or "PASS " in aggregate_text):
            raise SuiteError("installed aggregate-only output leaked details or false provenance")
        mismatch_aggregate = json.loads(_execute(
            [str(launcher), "evaluate", "demo_permissive.json",
             "--summary-only", "--format", "json"],
            work, env, expected_exit=1,
        ))
        if (mismatch_aggregate["summary"]["matched_fixture_labels"] != 0
                or "unrequested_forward" in json.dumps(mismatch_aggregate)):
            raise SuiteError("installed aggregate mismatch report failed or leaked case data")
        # Check real installed module and launcher output publication, not
        # just source-unit mocks. The fixture label mismatch must still exit 1.
        report_args = [
            "evaluate", "suite.json", "--format", "json",
            "--output", "installed_evaluation_report.json",
        ]
        _execute([sys.executable, "-S", "-m", "agent_trace_lab", *report_args], work, env)
        published = (work / "installed_evaluation_report.json").read_bytes()
        validate_evaluation(json.loads(published), 8)
        _execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", *report_args],
            work, env, expected_exit=2,
        )
        _execute([str(launcher), *report_args], work, env, expected_exit=2)
        if (work / "installed_evaluation_report.json").read_bytes() != published:
            raise SuiteError("installed evaluation report overwritten without opt-in")
        _execute([str(launcher), *report_args, "--overwrite"], work, env)
        if (work / "installed_evaluation_report.json").read_bytes() != published:
            raise SuiteError("installed evaluation explicit overwrite changed report semantics")
        mismatch_args = [
            "evaluate", "demo_permissive.json", "--format", "json",
            "--output", "installed_mismatched_report.json",
        ]
        _execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", *mismatch_args],
            work, env, expected_exit=1,
        )
        mismatch_report = (work / "installed_mismatched_report.json").read_bytes()
        if json.loads(mismatch_report)["summary"]["matched"] != 0:
            raise SuiteError("installed evaluation mismatch report was incorrect")
        _execute([str(launcher), *mismatch_args], work, env, expected_exit=2)
        _execute(
            [str(launcher), *mismatch_args, "--overwrite"],
            work, env, expected_exit=1,
        )
        input_bytes = (work / "suite.json").read_bytes()
        _execute(
            [str(launcher), "evaluate", "suite.json", "--output", "suite.json",
             "--overwrite"], work, env, expected_exit=2,
        )
        if (work / "installed_mismatched_report.json").read_bytes() != mismatch_report:
            raise SuiteError("installed mismatch overwrite changed report semantics")
        if (work / "suite.json").read_bytes() != input_bytes:
            raise SuiteError("installed evaluation report modified its input suite")
        if (untouched.read_bytes() != sentinel
                or list(work.glob(".agent-trace-report-*.tmp"))):
            raise SuiteError("installed evaluation modified unrelated files or left temporary files")
        policy_delta_args = [
            "compare-policies", "demo_permissive.json",
            "--candidate-policy", "compare_candidate_task_guarded.json",
            "--format", "json",
        ]
        module_delta = json.loads(_execute(
            [sys.executable, "-S", "-m", "agent_trace_lab", *policy_delta_args],
            work, env,
        ))
        console_delta = json.loads(_execute(
            [str(launcher), *policy_delta_args], work, env,
        ))
        if (module_delta != console_delta
                or module_delta["summary"]["total_cases"] != 1
                or module_delta["summary"]["changed"] != 1
                or module_delta["summary"]["allow_to_deny"] != 1
                or module_delta["cases"][0]["candidate_codes"] != ["TASK_GRANT_REQUIRED"]
                or "unrequested@example.invalid" in json.dumps(module_delta)):
            raise SuiteError("installed CLI policy delta comparison failed")
        alias_delta = json.loads(_execute(
            [sys.executable, "-S", "-m", "agent_trace_lab",
             *policy_delta_args, "--redact-case-ids"], work, env,
        ))
        console_alias_delta = json.loads(_execute(
            [str(launcher), *policy_delta_args, "--redact-case-ids"],
            work, env,
        ))
        if (alias_delta != console_alias_delta
                or alias_delta["summary"] != module_delta["summary"]
                or alias_delta["cases"][0]["id"] != "case_0001"
                or module_delta["cases"][0]["id"] == alias_delta["cases"][0]["id"]
                or "unrequested_forward" in json.dumps(alias_delta)
                or "unrequested@example.invalid" in json.dumps(alias_delta)):
            raise SuiteError("installed privacy mode did not redact case identifiers")
        # Actual installed console and module: compare report publication
        # must be identical to prior stdout and must fail closed on rerun.
        for fmt in ("json", "text"):
            compare_args = [
                "compare-policies", "demo_permissive.json",
                "--candidate-policy", "compare_candidate_task_guarded.json",
                "--format", fmt, "--redact-case-ids",
            ]
            existing_stdout = _execute(
                [sys.executable, "-S", "-m", "agent_trace_lab", *compare_args],
                work, env,
            )
            saved_name = f"installed_policy_delta_{fmt}.txt"
            stored_args = [*compare_args, "--output", saved_name]
            _execute([str(launcher), *stored_args], work, env)
            original = (work / saved_name).read_text(encoding="utf-8")
            if (original != existing_stdout
                    or "case_0001" not in original
                    or "unrequested_forward" in original
                    or "unrequested@example.invalid" in original):
                raise SuiteError("installed saved policy comparison differs or leaks case data")
            _execute(
                [sys.executable, "-S", "-m", "agent_trace_lab", *stored_args],
                work, env, expected_exit=2,
            )
            _execute([str(launcher), *stored_args], work, env, expected_exit=2)
            _execute([str(launcher), *stored_args, "--overwrite"], work, env)
            if (work / saved_name).read_text(encoding="utf-8") != original:
                raise SuiteError("installed policy report was replaced unexpectedly")
        # Opt-in aggregate report: actual installed module+console, no
        # case identifiers, aliases, tool names, or per-case reason codes.
        for fmt in ("json", "text"):
            aggregate_args = [
                "compare-policies", "demo_permissive.json",
                "--candidate-policy", "compare_candidate_task_guarded.json",
                "--summary-only", "--format", fmt,
            ]
            module_stdout = _execute(
                [sys.executable, "-S", "-m", "agent_trace_lab", *aggregate_args],
                work, env,
            )
            console_stdout = _execute(
                [str(launcher), *aggregate_args], work, env,
            )
            destination = f"installed_policy_aggregate_{fmt}.txt"
            written = _execute(
                [str(launcher), *aggregate_args, "--output", destination],
                work, env,
            )
            if (written or module_stdout != console_stdout
                    or (work / destination).read_text(encoding="utf-8") != module_stdout
                    or any(marker in module_stdout for marker in (
                        "unrequested_forward", "case_0001", "TASK_GRANT_REQUIRED",
                        "forward_email", "unrequested@example.invalid"))):
                raise SuiteError("installed aggregate comparison leaked case details")
            if fmt == "json":
                if json.loads(module_stdout) != {"summary": module_delta["summary"]}:
                    raise SuiteError("installed aggregate JSON changed policy counts")
            elif (len(module_stdout.splitlines()) != 1
                  or "allow->deny=1" not in module_stdout):
                raise SuiteError("installed aggregate text was not exactly one summary line")
            _execute(
                [str(launcher), *aggregate_args, "--output", destination],
                work, env, expected_exit=2,
            )
            _execute(
                [sys.executable, "-S", "-m", "agent_trace_lab",
                 *aggregate_args, "--output", destination, "--overwrite"],
                work, env,
            )
            if (work / destination).read_text(encoding="utf-8") != module_stdout:
                raise SuiteError("installed aggregate explicit overwrite changed counts")
        for protected in ("demo_permissive.json", "compare_candidate_task_guarded.json"):
            before = (work / protected).read_bytes()
            _execute(
                [str(launcher), "compare-policies", "demo_permissive.json",
                 "--candidate-policy", "compare_candidate_task_guarded.json",
                 "--output", protected, "--overwrite"],
                work, env, expected_exit=2,
            )
            if (work / protected).read_bytes() != before:
                raise SuiteError("installed policy report modified its input")
        if (untouched.read_bytes() != sentinel
                or list(work.glob(".agent-trace-compare-*.tmp"))):
            raise SuiteError("installed compare modified unrelated files or left temporary files")
        # Synthetic untrusted property name must never surface in the
        # installed module or console stderr. Keep this file temporary.
        private_marker = "PRIVATE_SYNTHETIC_JSON_KEY_98765"
        malformed = json.loads((work / "demo_permissive.json").read_text(encoding="utf-8"))
        malformed["cases"][0][private_marker] = "synthetic private value"
        (work / "malformed_demo.json").write_text(
            json.dumps(malformed), encoding="utf-8"
        )
        verify_installed_diagnostic(
            [sys.executable, "-S", "-m", "agent_trace_lab", "evaluate",
             "malformed_demo.json"], work, env, private_marker,
        )
        verify_installed_diagnostic(
            [str(launcher), "evaluate", "malformed_demo.json"],
            work, env, private_marker,
        )
        # Trigger real private-path failures on the installed distribution,
        # independently through the Python module and the actual launcher.
        # Every import command must redact the path without changing bytes.
        private_path_marker = "PRIVATE_SYNTHETIC_PATH_INSTALLED_44321"
        private_parent = work / private_path_marker
        private_parent.write_bytes(sentinel)  # not a directory
        missing_source = f"{private_path_marker}_MISSING.json"
        for kind, recorded, policy in import_cases:
            base_args = [
                f"import-{kind}", recorded, "--policy-suite", policy,
                "--case-id", "private_probe", "--expected", "allow",
                "--output", str(private_parent / "report.json"),
            ]
            missing_args = base_args.copy()
            missing_args[1] = missing_source
            for launcher_prefix in (
                [sys.executable, "-S", "-m", "agent_trace_lab"],
                [str(launcher)],
            ):
                verify_installed_io_diagnostic(
                    [*launcher_prefix, *base_args], work, env,
                    private_path_marker, "filesystem I/O operation failed",
                )
                verify_installed_io_diagnostic(
                    [*launcher_prefix, *missing_args], work, env,
                    private_path_marker, "filesystem I/O failure",
                )
        for prefix in (
            [sys.executable, "-S", "-m", "agent_trace_lab"],
            [str(launcher)],
        ):
            for args in (
                ["evaluate", missing_source],
                ["compare-policies", missing_source, "--candidate-policy",
                 "compare_candidate_task_guarded.json"],
            ):
                verify_installed_io_diagnostic(
                    [*prefix, *args], work, env,
                    private_path_marker, "filesystem I/O failure",
                )
        if (private_parent.read_bytes() != sentinel
                or untouched.read_bytes() != sentinel
                or list(work.glob(".agent-trace-import-*.tmp"))):
            raise SuiteError("installed private-path probe modified unrelated files")
    return {
        "status": "ISOLATED_INSTALLED_WHEEL_SMOKE_PASS",
        "release_metadata_version_verified": release_version,
        "release_source_links_and_license_verified": True,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "wheel_members_checked": len(names),
        "synthetic_dojo_calls_imported_not_executed": 2,
        "synthetic_policy_cases_matched": 8,
        "synthetic_permissive_expected_mismatch": True,
        "synthetic_task_scoped_cases_matched": 5,
        "synthetic_task_scoped_real_grants_authenticated": False,
        "installed_console_launcher_verified": True,
        "installed_console_matches_module_results": True,
        "installed_policy_delta_comparison_verified": True,
        "installed_policy_delta_case_id_redaction_verified": True,
        "installed_policy_delta_atomic_report_output_verified": True,
        "installed_policy_delta_summary_only_verified": True,
        "installed_schema_diagnostics_redacted": True,
        "installed_cli_private_io_paths_redacted": True,
        "installed_import_output_no_clobber_verified": True,
        "installed_evaluation_output_no_clobber_verified": True,
        "installed_evaluation_mismatch_exit_and_overwrite_verified": True,
        "installed_aggregate_only_report_verified": True,
        "installed_structural_only_validation_verified": True,
        "installed_otlp_policy_only_audit_verified": True,
        "installed_otlp_policy_only_ci_exit_gate_verified": True,
        "installed_import_explicit_overwrite_verified": True,
        "installed_import_formats_verified": len(import_cases) - 1,
        "installed_import_commands_verified": len(import_cases),
        "installed_responses_sequence_preserves_order_verified": True,
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
