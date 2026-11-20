"""Synthetic policy-delta comparisons; never treat fixture labels as permissions."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.engine import compare_policies
from agent_trace_lab.schema import SuiteError, load_json_document, load_suite

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples" / "demo_permissive.json"
CANDIDATE = ROOT / "examples" / "compare_candidate_task_guarded.json"
_UNSET = object()


class PolicyComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = load_suite(BASE)
        self.candidate = load_json_document(CANDIDATE)

    def compare(self, base=None, candidate=_UNSET):
        return compare_policies(
            self.base if base is None else base,
            self.candidate if candidate is _UNSET else candidate,
        )

    def test_same_trace_transitions_allow_to_deny(self):
        report = self.compare()
        self.assertEqual(report["summary"], {
            "total_cases": 1, "changed": 1, "allow_to_deny": 1,
            "deny_to_allow": 0, "unchanged": 0,
            "candidate_ignored_grant_cases": 0,
        })
        self.assertEqual(report["cases"][0], {
            "id": "unrequested_forward", "baseline": "allow",
            "candidate": "deny", "changed": True, "baseline_codes": [],
            "candidate_codes": ["TASK_GRANT_REQUIRED"],
        })
        self.assertNotIn("unrequested@example.invalid", json.dumps(report))
        self.assertNotIn("synthetic_message_01", json.dumps(report))
        self.assertNotIn("forward_email", json.dumps(report))
        self.assertNotIn("accuracy", json.dumps(report))

    def test_opt_in_redaction_aliases_ids_but_preserves_decisions(self):
        self.base["cases"][0]["id"] = "PRIVATE_SYNTHETIC_CASE_98765"
        self.base["cases"].append(copy.deepcopy(self.base["cases"][0]))
        self.base["cases"][1]["id"] = "PRIVATE_OTHER_CASE_12345"
        self.base["cases"][1]["trace"] = []
        original = copy.deepcopy(self.base)
        public = compare_policies(self.base, self.candidate, redact_case_ids=True)
        private = self.compare()
        self.assertEqual([row["id"] for row in public["cases"]], ["case_0001", "case_0002"])
        self.assertEqual(public["summary"], private["summary"])
        self.assertEqual(
            [(row["baseline"], row["candidate"], row["changed"]) for row in public["cases"]],
            [(row["baseline"], row["candidate"], row["changed"]) for row in private["cases"]],
        )
        self.assertNotIn("PRIVATE_SYNTHETIC_CASE", json.dumps(public))
        self.assertNotIn("PRIVATE_OTHER_CASE", json.dumps(public))
        self.assertEqual(self.base, original)
        self.assertEqual(public, compare_policies(self.base, self.candidate, redact_case_ids=True))

    def test_redaction_mixed_schema_never_exposes_grant_references(self):
        base = load_suite(ROOT / "examples" / "demo_task_scoped.json")
        for index, case in enumerate(base["cases"]):
            case["id"] = f"PRIVATE_CASE_{index + 1}"
        candidate_source = load_json_document(BASE)
        candidate = {"schema_version": "1.0", "policy": candidate_source["policy"]}
        result = compare_policies(base, candidate, redact_case_ids=True)
        text = json.dumps(result)
        self.assertEqual(result["summary"]["candidate_ignored_grant_cases"], 3)
        self.assertEqual(result["cases"][0]["id"], "case_0001")
        self.assertEqual(result["cases"][4]["id"], "case_0005")
        self.assertNotIn("PRIVATE_CASE", text)
        self.assertNotIn("self-authored-fictional-demo-only", text)
        self.assertNotIn("demo_grant_", text)
        self.assertNotIn("unrequested@example.invalid", text)

    def test_invalid_baseline_cannot_be_repaired_by_aliasing(self):
        self.base["cases"][0]["id"] = "INVALID PRIVATE CASE"
        with self.assertRaises(SuiteError) as error:
            compare_policies(self.base, self.candidate, redact_case_ids=True)
        self.assertNotIn("INVALID PRIVATE CASE", str(error.exception))

    def test_cli_redacted_json_and_text_never_print_original_case_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            suite = copy.deepcopy(self.base)
            suite["cases"][0]["id"] = "PRIVATE_SYNTHETIC_CASE_98765"
            local = Path(folder) / "private_suite.json"
            local.write_text(json.dumps(suite), encoding="utf-8")
            before = local.read_bytes()
            common = [
                sys.executable, "-m", "agent_trace_lab", "compare-policies",
                str(local), "--candidate-policy", str(CANDIDATE), "--redact-case-ids",
            ]
            for format_args in ([], ["--format", "json"]):
                with self.subTest(format=format_args):
                    run = subprocess.run(
                        [*common, *format_args], cwd=ROOT, text=True,
                        capture_output=True, timeout=15,
                    )
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertIn("case_0001", run.stdout)
                    self.assertNotIn("PRIVATE_SYNTHETIC_CASE_98765", run.stdout + run.stderr)
                    self.assertNotIn("unrequested@example.invalid", run.stdout + run.stderr)
            self.assertEqual(local.read_bytes(), before)
            # Backwards compatible local diagnostics retain original case IDs.
            normal = subprocess.run(
                common[:-1], cwd=ROOT, text=True, capture_output=True, timeout=15,
            )
            self.assertEqual(normal.returncode, 0, normal.stderr)
            self.assertIn("PRIVATE_SYNTHETIC_CASE_98765", normal.stdout)

    def test_same_policy_produces_zero_delta(self):
        proposed = {
            "schema_version": self.base["schema_version"],
            "policy": copy.deepcopy(self.base["policy"]),
        }
        report = self.compare(candidate=proposed)
        self.assertEqual(report["summary"]["changed"], 0)
        self.assertEqual(report["summary"]["unchanged"], 1)

    def test_inputs_are_unchanged_and_output_deterministic(self):
        original = copy.deepcopy(self.base)
        candidate = copy.deepcopy(self.candidate)
        expected = self.compare()
        self.assertEqual(self.compare(), expected)
        self.assertEqual(self.base, original)
        self.assertEqual(self.candidate, candidate)

    def test_expected_fixture_labels_do_not_affect_policy_delta(self):
        original = self.compare()
        self.base["cases"][0]["expected"] = "allow"
        self.assertEqual(self.compare(), original)

    def test_deny_to_allow_reversal_is_detected(self):
        self.base["policy"] = copy.deepcopy(self.candidate["policy"])
        self.base["schema_version"] = "1.1"
        proposed = load_json_document(BASE)
        candidate = {"schema_version": "1.0", "policy": proposed["policy"]}
        report = self.compare(candidate=candidate)
        self.assertEqual(report["summary"]["deny_to_allow"], 1)
        self.assertEqual(report["summary"]["allow_to_deny"], 0)

    def test_switch_to_schema_10_explicitly_counts_ignored_grants(self):
        base = load_suite(ROOT / "examples" / "demo_task_scoped.json")
        proposed = load_json_document(BASE)
        candidate = {"schema_version": "1.0", "policy": proposed["policy"]}
        report = self.compare(base=base, candidate=candidate)
        self.assertEqual(report["summary"]["total_cases"], 5)
        self.assertEqual(report["summary"]["candidate_ignored_grant_cases"], 3)
        self.assertEqual(report["summary"]["deny_to_allow"], 3)
        self.assertEqual(report["summary"]["unchanged"], 2)
        self.assertEqual(base["cases"][1]["task_authorization"]["task_id"], "demo_approved")

    def test_invalid_candidate_document_fields_fail_closed(self):
        for payload in (
            None, [], {"policy": self.candidate["policy"]},
            {"schema_version": "9.0", "policy": self.candidate["policy"]},
            {**self.candidate, "cases": []},
            {"schema_version": "1.1", "policy": {"tools": {}, "max_actions": 5}},
        ):
            with self.subTest(payload=type(payload).__name__), self.assertRaises(SuiteError):
                self.compare(candidate=payload)

    def test_invalid_baseline_not_mistaken_for_candidate_policy(self):
        broken = copy.deepcopy(self.base)
        broken["cases"][0]["trace"][0]["arguments"] = []
        with self.assertRaises(SuiteError):
            self.compare(base=broken)

    def test_multiple_cases_preserve_original_alignment(self):
        self.base["cases"].append(copy.deepcopy(self.base["cases"][0]))
        self.base["cases"][1]["id"] = "second"
        self.base["cases"][1]["trace"] = []
        report = self.compare()
        self.assertEqual([row["id"] for row in report["cases"]],
                         ["unrequested_forward", "second"])
        self.assertEqual(report["summary"]["changed"], 1)
        self.assertEqual(report["summary"]["unchanged"], 1)

    def test_cli_text_json_and_error_codes_with_no_file_mutations(self):
        common = [
            sys.executable, "-m", "agent_trace_lab", "compare-policies",
            str(BASE), "--candidate-policy", str(CANDIDATE),
        ]
        text_result = subprocess.run(
            common, cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(text_result.returncode, 0, text_result.stderr)
        self.assertIn("allow->deny=1", text_result.stdout)
        self.assertNotIn("unrequested@example.invalid", text_result.stdout)
        json_result = subprocess.run(
            [*common, "--format", "json"], cwd=ROOT, capture_output=True,
            text=True, timeout=15,
        )
        self.assertEqual(json_result.returncode, 0, json_result.stderr)
        self.assertEqual(json.loads(json_result.stdout)["summary"]["changed"], 1)
        with tempfile.TemporaryDirectory() as folder:
            corrupted = Path(folder) / "candidate.json"
            corrupted.write_text('{"schema_version":"1.1","policy":null}', encoding="utf-8")
            bad = subprocess.run(
                [*common[:5], "--candidate-policy", str(corrupted)],
                cwd=ROOT, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
