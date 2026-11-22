"""Synthetic fail-closed OTLP argument-omission research check (ATL-004DQ).

Writes only generated fixtures/receipt into git-ignored artifacts. No tool
actions are executed; no real trace, external SDK, network or API is needed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "artifacts" / "atl004dq_external_job_probe_20261122"
TRACE = ROOT / "examples" / "otlp_spans.json"
POLICY = ROOT / "examples" / "otlp_audit_policy.json"
MARKER = "SYNTH_ONLY_DO_NOT_PRINT_004DQ"


def audit(trace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, "-m", "agent_trace_lab", "audit-otlp", str(trace),
            "--policy-file", str(POLICY), "--fail-on-deny",
        ],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )


def main() -> None:
    LAB.mkdir(parents=True, exist_ok=True)
    record = copy.deepcopy(json.loads(TRACE.read_text(encoding="utf-8")))
    span = record["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
    span["attributes"] = [
        attr for attr in span["attributes"]
        if attr["key"] != "gen_ai.tool.call.arguments"
    ]
    span["attributes"].append({
        "key": "synthetic.private.marker",
        "value": {"stringValue": MARKER},
    })
    fixture = LAB / "missing-opt-in-arguments.json"
    fixture.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    baseline, missing = audit(TRACE), audit(fixture)
    if baseline.returncode != 0:
        raise AssertionError("baseline example did not pass policy")
    report = json.loads(baseline.stdout)
    if report["actual"] != "allow" or report["trace_completeness_verified"] is not False:
        raise AssertionError("baseline verdict/completeness contract changed")
    if missing.returncode != 2 or missing.stdout or "Traceback" in missing.stderr:
        raise AssertionError("missing arguments did not fail closed without output")
    if MARKER in missing.stdout + missing.stderr:
        raise AssertionError("synthetic private marker was disclosed")
    if "arguments were not recorded" not in missing.stderr:
        raise AssertionError("expected bounded diagnostic was not emitted")

    receipt = {
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "baseline_exit": baseline.returncode,
        "baseline_actual": report["actual"],
        "baseline_trace_completeness_verified": report["trace_completeness_verified"],
        "missing_args_exit": missing.returncode,
        "missing_args_stdout_empty": not missing.stdout,
        "private_marker_hidden": MARKER not in missing.stdout + missing.stderr,
        "no_tool_execution": True,
        "result": "SYNTHETIC_FAIL_CLOSED_EXISTING_BEHAVIOR",
    }
    (LAB / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
