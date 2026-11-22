"""Copyable, offline CI consumer proof for audit-otlp exit codes.

Uses only self-authored repository examples and disposable temporary files.
It never runs recorded tools, saves an audit report, or asserts trace closure.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "examples" / "otlp_spans.json"
POLICY = ROOT / "examples" / "otlp_audit_policy.json"
UNVERIFIED = (
    "ground_truth_available",
    "user_authorization_verified",
    "security_metrics_available",
    "trace_completeness_verified",
    "recorded_actions_executed",
)


def require(condition: bool, description: str) -> None:
    if not condition:
        raise SystemExit(f"OTLP_CI_CONSUMER_DEMO_FAIL: {description}")


def audit(trace: Path, policy: Path, *, fail_on_deny: bool) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable, "-m", "agent_trace_lab", "audit-otlp",
        str(trace), "--policy-file", str(policy), "--format", "json",
    ]
    if fail_on_deny:
        command.append("--fail-on-deny")
    return subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=20,
        check=False,
    )


def validated_report(result: subprocess.CompletedProcess[str], actual: str) -> dict:
    require(result.stderr == "", "unexpected stderr for a valid audit")
    report = json.loads(result.stdout)
    require(report.get("actual") == actual, "unexpected policy verdict")
    require(report.get("recorded_action_count") == 2, "wrong tool-call count")
    require(all(report.get(key) is False for key in UNVERIFIED), "unverified claim missing")
    require(not any(key in report for key in ("expected", "accuracy", "trace", "arguments")),
            "private or labeled fields in report")
    require("files.read" not in result.stdout, "recorded tool name disclosed")
    return report


def main() -> None:
    allowed = audit(TRACE, POLICY, fail_on_deny=True)
    require(allowed.returncode == 0, "allow must exit 0")
    require(validated_report(allowed, "allow")["violations"] == [],
            "allow must have no violations")

    with tempfile.TemporaryDirectory(prefix="atl-ci-consumer-") as folder:
        scratch = Path(folder)
        restrictive = copy.deepcopy(json.loads(POLICY.read_text(encoding="utf-8")))
        restrictive["policy"]["max_actions"] = 1
        deny_policy = scratch / "deny-policy.json"
        deny_policy.write_text(json.dumps(restrictive), encoding="utf-8")

        default_deny = audit(TRACE, deny_policy, fail_on_deny=False)
        flagged_deny = audit(TRACE, deny_policy, fail_on_deny=True)
        require(default_deny.returncode == 0, "legacy deny must exit 0")
        require(flagged_deny.returncode == 1, "opt-in deny must exit 1")
        require(flagged_deny.stdout == default_deny.stdout,
                "opt-in flag changed the report body")
        require(validated_report(flagged_deny, "deny")["violations"] == [
            {"event_index": 1, "code": "ACTION_LIMIT_EXCEEDED"},
        ], "wrong deny finding")

        malformed = scratch / "malformed.json"
        malformed.write_text("{", encoding="utf-8")
        invalid = audit(malformed, POLICY, fail_on_deny=True)
        require(invalid.returncode == 2, "malformed trace must exit 2")
        require(invalid.stdout == "", "malformed trace printed a partial report")
        require("Traceback" not in invalid.stderr, "malformed trace leaked a traceback")

    print("OTLP_CI_CONSUMER_DEMO_PASS allow=0 deny_default=0 deny_flag=1 malformed=2")
    print("TRACE_COMPLETENESS_UNVERIFIED; USER_AUTHORIZATION_UNVERIFIED; NO_TOOLS_EXECUTED")


if __name__ == "__main__":
    main()
