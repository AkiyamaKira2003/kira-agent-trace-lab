"""Offline negative controls for preregistration and sampling evidence."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from agent_trace_lab.schema import SuiteError
from scripts.audit_agentdojo_strata import (
    _read_json_bounded, extract_run_summary, gather, planned_slots, report,
    validate_manifest, validate_spec, verify_upstream,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "docs/agentdojo_stratified_preregistration.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "docs/agentdojo_stratified_exposures.json").read_text(encoding="utf-8"))


class StratifiedTests(unittest.TestCase):
    def test_preregistration_and_exact_cartesian_product(self):
        spec = validate_spec(copy.deepcopy(SPEC))
        slots = planned_slots(spec)
        self.assertEqual(len(slots), 24)
        self.assertEqual(len(set(r["source_path"] for r in slots)), 24)
        self.assertEqual([r["condition"] for r in slots[:3]],
                         ["baseline", "direct", "important_instructions"])
        self.assertEqual([r["task_index"] for r in slots[:6]], [0, 0, 0, 1, 1, 1])
        self.assertEqual([slots[i]["suite"] for i in (0, 6, 12, 18)],
                         ["banking", "slack", "travel", "workspace"])

    def test_rule_change_cannot_be_disguised_as_new_sample(self):
        for field, changed in (
            ("task_indices", [0, 2]),
            ("suite_universe", ["banking", "travel", "workspace"]),
            ("max_file_bytes", 999999),
            ("expected_slots", 20),
        ):
            with self.subTest(field=field):
                spec = copy.deepcopy(SPEC)
                spec[field] = changed
                with self.assertRaisesRegex(SuiteError, "precommitted"):
                    validate_spec(spec)

    def test_attack_strategy_and_file_cannot_be_replaced(self):
        spec = copy.deepcopy(SPEC)
        spec["conditions"][1]["relative_path"] = "direct/injection_task_1.json"
        with self.assertRaisesRegex(SuiteError, "conditions"):
            validate_spec(spec)

    def test_manifest_fixed_denominator_and_no_reviewers(self):
        value = validate_manifest(SPEC, copy.deepcopy(MANIFEST))
        self.assertEqual(len(value["records"]), 24)
        self.assertEqual(value["independent_reviewers"], [])
        self.assertEqual(value["adjudication_state"], "not_started")
        result = report(SPEC, value, online=False)
        self.assertEqual(result["planned_slots"], 24)
        self.assertEqual(result["availability"], {"missing": 4, "present": 20})
        self.assertEqual(result["suite_counts"], {
            "banking": 6, "slack": 6, "travel": 6, "workspace": 6,
        })
        self.assertEqual(result["condition_counts"], {
            "baseline": 8, "direct": 8, "important_instructions": 8,
        })
        self.assertEqual(result["simulated_scope_reviews_pending"], 24)
        self.assertEqual(result["real_human_grant_abstentions"], 24)
        self.assertEqual(result["independent_reviewers"], 0)
        self.assertEqual(result["policy_verdicts_computed"], 0)
        self.assertFalse(result["population_accuracy_claimed"])
        self.assertFalse(result["recorded_actions_executed"])
        self.assertEqual(report(SPEC, value, online=True)["readable_run_hashes_rechecked"], 20)
        self.assertEqual(report(SPEC, value, online=True, capture=True)["readable_run_hashes_rechecked"], 0)
        self.assertEqual(report(SPEC, value, online=True, capture=True)["status"], "UPSTREAM_24_SLOTS_CAPTURED")

    def test_missing_exposures_are_explicit_not_zero_call_runs(self):
        missing = [r for r in MANIFEST["records"] if r["status"] == "missing"]
        self.assertEqual(len(missing), 4)
        self.assertEqual({(r["suite"], r["task_index"], r["condition"]) for r in missing}, {
            ("slack", 0, "direct"),
            ("slack", 0, "important_instructions"),
            ("slack", 1, "direct"),
            ("slack", 1, "important_instructions"),
        })
        self.assertTrue(all(r["sha256"] is None and r["size_bytes"] is None for r in missing))

    def test_cannot_remove_or_reorder_exposures(self):
        for name, change in (
            ("drop", lambda m: m["records"].pop(8)),
            ("swap", lambda m: m["records"].reverse()),
            ("switch_task", lambda m: m["records"][0].update(task_index=1)),
            ("switch_path", lambda m: m["records"][0].update(source_path="../something")),
        ):
            with self.subTest(name=name):
                m = copy.deepcopy(MANIFEST)
                change(m)
                with self.assertRaises(SuiteError):
                    validate_manifest(SPEC, m)

    def test_cannot_spoof_reviewers_or_consent(self):
        changes = [
            ("independent_reviewers", ["reviewer_A", "reviewer_B"]),
            ("adjudication_state", "completed"),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                m = copy.deepcopy(MANIFEST)
                m[field] = value
                with self.assertRaisesRegex(SuiteError, "reviewer"):
                    validate_manifest(SPEC, m)
        for field, label in (
            ("real_human_authorization_label", "allow"),
            ("simulated_scope_review", "within_scope"),
        ):
            with self.subTest(field=field):
                m = copy.deepcopy(MANIFEST)
                m["records"][0][field] = label
                with self.assertRaisesRegex(SuiteError, "grants or reviewers"):
                    validate_manifest(SPEC, m)

    def test_no_fabricated_hashes_or_outcomes_on_missing_slots(self):
        for field, value in (
            ("sha256", "a" * 64),
            ("observed_tools", ["send_money"]),
            ("publisher_utility", False),
        ):
            with self.subTest(field=field):
                m = copy.deepcopy(MANIFEST)
                m["records"][7][field] = value
                with self.assertRaises(SuiteError):
                    validate_manifest(SPEC, m)

    def test_no_invalid_hash_or_size_on_present_slots(self):
        for field, value in (("sha256", "abc"), ("size_bytes", -1)):
            with self.subTest(field=field):
                m = copy.deepcopy(MANIFEST)
                m["records"][0][field] = value
                with self.assertRaisesRegex(SuiteError, "fingerprints"):
                    validate_manifest(SPEC, m)

    def test_parser_accepts_bounded_synthetic_envelope(self):
        slot = planned_slots(SPEC)[0]
        record = {
            "suite_name": "banking", "user_task_id": "user_task_0",
            "attack_type": None, "injection_task_id": None,
            "utility": True, "security": True,
            "messages": [{"role": "assistant", "tool_calls": [
                {"id": "call0", "function": "read_file", "args": {"path": "opaque-no-output"}},
            ]}],
        }
        metadata = extract_run_summary(slot, json.dumps(record).encode())
        self.assertEqual(metadata["observed_tools"], ["read_file"])
        self.assertNotIn("opaque-no-output", str(metadata))

    def test_parser_rejects_wrong_task_or_injection_status(self):
        slot = planned_slots(SPEC)[0]
        record = {
            "suite_name": "banking", "user_task_id": "user_task_0",
            "attack_type": None, "injection_task_id": None,
            "utility": True, "security": True,
            "messages": [{"role": "assistant", "tool_calls": []}],
        }
        for name, value in (
            ("user_task_id", "user_task_1"),
            ("attack_type", "direct"),
            ("security", "true"),
        ):
            with self.subTest(name=name):
                mutated = dict(record)
                mutated[name] = value
                with self.assertRaises(SuiteError):
                    extract_run_summary(slot, json.dumps(mutated).encode())

    def test_parser_rejects_nonassistant_tool_calls(self):
        slot = planned_slots(SPEC)[0]
        record = {
            "suite_name": "banking", "user_task_id": "user_task_0",
            "attack_type": None, "injection_task_id": None,
            "utility": True, "security": True,
            "messages": [{"role": "tool", "tool_calls": [
                {"id": "1", "function": "send_money", "args": {}},
            ]}],
        }
        with self.assertRaisesRegex(SuiteError, "assistant"):
            extract_run_summary(slot, json.dumps(record).encode())

    def test_verify_requires_exact_full_source_summary(self):
        with patch("scripts.audit_agentdojo_strata.gather", return_value=copy.deepcopy(MANIFEST["records"])):
            verify_upstream(SPEC, MANIFEST)
        changed = copy.deepcopy(MANIFEST["records"])
        changed[0]["observed_tools"].append("fake_call")
        with patch("scripts.audit_agentdojo_strata.gather", return_value=changed):
            with self.assertRaisesRegex(SuiteError, "differs"):
                verify_upstream(SPEC, MANIFEST)

    def test_metadata_bound_and_duplicate_key_rejection(self):
        spec_path = ROOT / "docs" / "agentdojo_stratified_preregistration.json"
        with self.assertRaisesRegex(SuiteError, "size cap"):
            _read_json_bounded(spec_path, 1)
        from scripts.audit_agentdojo_sampling import _parse_json
        with self.assertRaises(SuiteError):
            _parse_json(b'{"a":1,"a":2}')


if __name__ == "__main__":
    unittest.main()
