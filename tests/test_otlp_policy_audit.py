"""ATL-004DN: no caller labels or human authorization inferred from saved OTLP."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.schema import load_json_document, load_suite
from agent_trace_lab.engine import evaluate_policy_trace, evaluate_suite
from agent_trace_lab.otlp import import_otlp, parse_otlp_tool_trace


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "examples" / "otlp_spans.json"
BASE_POLICY = ROOT / "examples" / "suite.json"


class OtlpPolicyAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.trace = load_json_document(ORIGINAL)
        self.policy_document = {
            "schema_version": "1.0",
            "policy": load_suite(BASE_POLICY)["policy"],
        }

    def run_audit(self, *, trace=None, policy=None, format="json"):
        trace_file = self.folder / "recorded.json"
        policy_file = self.folder / "policy.json"
        trace_file.write_text(json.dumps(self.trace if trace is None else trace), encoding="utf-8")
        policy_file.write_text(json.dumps(
            self.policy_document if policy is None else policy), encoding="utf-8")
        return subprocess.run([
            sys.executable, "-m", "agent_trace_lab", "audit-otlp",
            str(trace_file), "--policy-file", str(policy_file),
            "--format", format,
        ], cwd=ROOT, capture_output=True, text=True, timeout=15)

    def test_one_command_without_label_returns_only_policy_decision(self):
        result = self.run_audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["actual"], "allow")
        self.assertEqual(payload["recorded_action_count"], 2)
        self.assertEqual(payload["violations"], [])
        for flag in (
            "ground_truth_available", "user_authorization_verified",
            "security_metrics_available", "trace_completeness_verified",
            "recorded_actions_executed",
        ):
            self.assertIs(payload[flag], False)
        for forbidden in ("expected", "confusion", "accuracy", "precision", "recall",
                          "matched", "cases", "trace", "arguments", "tool", "tp", "tn"):
            self.assertNotIn(forbidden, payload)
        self.assertEqual(result.stdout, self.run_audit().stdout)

    def test_same_trace_different_policy_changes_verdict_not_truth_label(self):
        changed = copy.deepcopy(self.policy_document)
        changed["policy"]["max_actions"] = 1
        result = self.run_audit(policy=changed)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["actual"], "deny")
        self.assertEqual(report["violations"], [
            {"event_index": 1, "code": "ACTION_LIMIT_EXCEEDED"},
        ])
        self.assertIs(report["ground_truth_available"], False)
        self.assertNotIn("expected", result.stdout)

    def test_schema_11_guarded_call_requires_external_grant(self):
        guarded = copy.deepcopy(self.policy_document)
        guarded["schema_version"] = "1.1"
        guarded["policy"]["task_guarded_tools"] = ["files.read"]
        result = self.run_audit(policy=guarded)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["actual"], "deny")
        self.assertIn(
            {"event_index": 0, "code": "TASK_GRANT_REQUIRED"},
            report["violations"],
        )
        self.assertFalse(report["user_authorization_verified"])

    def test_path_policy_rejects_outside_workspace_without_private_values(self):
        trace = copy.deepcopy(self.trace)
        tool_span = trace["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
        tool_span["attributes"][2]["value"] = {
            "stringValue": json.dumps({"path": "/synthetic/private_secret/marker_872"})
        }
        result = self.run_audit(trace=trace)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["actual"], "deny")
        self.assertIn({"event_index": 0, "code": "PATH_OUTSIDE_ROOT"}, report["violations"])
        self.assertNotIn("private_secret", result.stdout + result.stderr)
        self.assertNotIn("files.read", result.stdout)

    def test_invalid_recorded_ids_or_missing_arguments_fail_closed(self):
        for defect in ("duplicate", "mixed_trace", "missing_arguments", "missing_timestamp"):
            with self.subTest(defect=defect):
                trace = copy.deepcopy(self.trace)
                spans = trace["resourceSpans"][0]["scopeSpans"][0]["spans"]
                if defect == "duplicate":
                    spans[2]["spanId"] = spans[1]["spanId"]
                elif defect == "mixed_trace":
                    spans[2]["traceId"] = "f" * 32
                elif defect == "missing_arguments":
                    spans[1]["attributes"] = spans[1]["attributes"][:2]
                else:
                    spans[1].pop("startTimeUnixNano")
                result = self.run_audit(trace=trace)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("Traceback", result.stderr)

    def test_trace_arguments_and_unknown_tool_names_are_not_disclosed(self):
        trace = copy.deepcopy(self.trace)
        spans = trace["resourceSpans"][0]["scopeSpans"][0]["spans"]
        spans[2]["attributes"][1]["value"] = {
            "stringValue": "synthetic_private_tool_marker_99871"
        }
        spans[2]["attributes"][2]["value"] = {
            "stringValue": json.dumps({"secret_398": "synthetic_private_argument_784"})
        }
        result = self.run_audit(trace=trace)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["actual"], "deny")
        self.assertIn(
            {"event_index": 1, "code": "TOOL_NOT_ALLOWED"},
            report["violations"],
        )
        self.assertNotIn("synthetic_private", result.stdout + result.stderr)
        self.assertNotIn("secret_398", result.stdout + result.stderr)

    def test_invalid_policy_and_legacy_import_requirements_unchanged(self):
        malformed = {"schema_version": "1.0", "policy": {"tools": {}, "max_actions": 0}}
        result = self.run_audit(policy=malformed)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        legacy = subprocess.run([
            sys.executable, "-m", "agent_trace_lab", "import-otlp",
            str(ORIGINAL), "--policy-suite", str(BASE_POLICY),
            "--case-id", "synthetic", "--output", str(self.folder / "legacy.json"),
        ], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(legacy.returncode, 2)
        self.assertFalse((self.folder / "legacy.json").exists())

    def test_text_mode_explicitly_disclaims_completeness_and_ground_truth(self):
        result = self.run_audit(format="text")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("allow", result.stdout)
        self.assertIn("unverified", result.stdout)
        self.assertNotIn("files.read", result.stdout)
        self.assertNotIn("docs.search", result.stdout)

    def test_policy_only_scanner_matches_existing_labeled_verdicts(self):
        trace = parse_otlp_tool_trace(self.trace)
        for guarded in (False, True):
            with self.subTest(guarded=guarded):
                policy = copy.deepcopy(self.policy_document["policy"])
                if guarded:
                    policy["task_guarded_tools"] = ["files.read"]
                version = "1.1" if guarded else "1.0"
                audit = evaluate_policy_trace(policy, trace, schema_version=version)
                labeled = evaluate_suite(import_otlp(
                    self.trace, policy=policy, case_id="synthetic_legacy",
                    expected="deny",  # Only the old labeled fixture supplies a label.
                ))["cases"][0]
                self.assertEqual(audit["actual"], labeled["actual"])
                self.assertEqual(
                    audit["violations"],
                    [{"event_index": item["event_index"], "code": item["code"]}
                     for item in labeled["violations"]],
                )
                self.assertNotIn("expected", audit)

    def test_strict_policy_only_envelope_rejects_unknown_fields(self):
        policy = copy.deepcopy(self.policy_document)
        policy["expected"] = "allow"
        result = self.run_audit(policy=policy)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
