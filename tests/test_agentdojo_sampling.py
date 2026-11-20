"""Negative controls for reproducible, non-consent AgentDojo sampling."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from agent_trace_lab.schema import SuiteError
from scripts.audit_agentdojo_sampling import (
    _parse_json, _selected_from_suites, check_directory, check_run,
    report, validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "docs" / "agentdojo_sampling_manifest.json").read_text(encoding="utf-8"))


def sample_record(entry):
    return {
        "suite_name": entry["suite"],
        "user_task_id": "user_task_0",
        "injection_task_id": "injection_task_0" if entry["condition"] == "injection_attempt" else None,
        "attack_type": "important_instructions" if entry["condition"] == "injection_attempt" else None,
        "utility": entry["publisher_utility"],
        "security": entry["publisher_security_field"],
        "error": None,
        "messages": [{"role": "assistant", "tool_calls": [
            {"id": f"call-{i}", "function": tool, "args": {}}
            for i, tool in enumerate(entry["observed_tools"])
        ]}],
    }


class SamplingTests(unittest.TestCase):
    def test_rule_and_balance_no_auth_claim(self):
        value = validate_manifest(copy.deepcopy(DATA))
        offline = report(value, upstream_verified=False)
        self.assertEqual(offline["status"], "OFFLINE_SAMPLING_MANIFEST_VALIDATED")
        self.assertEqual(offline["exposure_cohorts"], {"injection_attempt": 2, "no_injection": 2})
        self.assertEqual(offline["source_families"], {"banking": 2, "workspace": 2})
        self.assertEqual(offline["human_authorization_abstentions"], 4)
        self.assertEqual(offline["simulated_scope_abstentions"], 4)
        self.assertEqual(offline["policy_verdicts_computed"], 0)
        self.assertFalse(offline["population_accuracy_claimed"])
        verified = report(value, upstream_verified=True)
        self.assertEqual(verified["source_files_hash_verified"], 4)

    def test_fixed_rule_is_derived_from_directory_names(self):
        self.assertEqual(_selected_from_suites(DATA["available_suites"]), ["banking", "workspace"])
        check_directory(DATA["available_suites"])

    def test_noncanonical_suite_universe_rejected(self):
        for suites in (["banking", "workspace"], ["workspace", "banking"], ["banking", "slack", "travel", "workspace", "extra"]):
            with self.subTest(suites=suites):
                bad = copy.deepcopy(DATA)
                bad["available_suites"] = suites
                with self.assertRaisesRegex(SuiteError, "universe"):
                    validate_manifest(bad)

    def test_swapped_or_misclassified_cohort_rejected(self):
        for field, value in (("suite", "workspace"), ("condition", "no_injection")):
            with self.subTest(field=field):
                bad = copy.deepcopy(DATA)
                bad["records"][1][field] = value
                with self.assertRaisesRegex(SuiteError, "selection or cohort"):
                    validate_manifest(bad)

    def test_path_and_source_hash_guard(self):
        for field, value, message in (
            ("source_path", "../../outside.json", "noncanonical"),
            ("sha256", "invalid", "hash"),
        ):
            with self.subTest(field=field):
                bad = copy.deepcopy(DATA)
                bad["records"][0][field] = value
                with self.assertRaisesRegex(SuiteError, message):
                    validate_manifest(bad)

    def test_outcome_flags_must_remain_boolean(self):
        bad = copy.deepcopy(DATA)
        bad["records"][0]["publisher_utility"] = 1
        with self.assertRaisesRegex(SuiteError, "booleans"):
            validate_manifest(bad)

    def test_never_relabel_exposure_as_authorization(self):
        for field in ("simulated_authorization_label", "real_human_authorization_label"):
            with self.subTest(field=field):
                bad = copy.deepcopy(DATA)
                bad["records"][2][field] = "deny"
                with self.assertRaisesRegex(SuiteError, "consent or simulated"):
                    validate_manifest(bad)

    def test_all_four_observed_sequences_match(self):
        for record in DATA["records"]:
            with self.subTest(family=record["suite"],condition=record["condition"]):
                check_run(record, sample_record(record))

    def test_attack_presence_not_inferred_from_publisher_security(self):
        # security=True also on the baseline; this is not a user-grant
        # or stand-alone successful-attack classification.
        self.assertTrue(all(row["publisher_security_field"] is True for row in DATA["records"]))
        bad = sample_record(DATA["records"][0])
        bad["attack_type"] = "important_instructions"
        with self.assertRaisesRegex(SuiteError, "cohort"):
            check_run(DATA["records"][0], bad)

    def test_injected_call_order_mismatch_rejected(self):
        row = DATA["records"][1]
        fake = sample_record(row)
        fake["messages"][0]["tool_calls"].reverse()
        with self.assertRaisesRegex(SuiteError, "ordered action"):
            check_run(row, fake)

    def test_nonassistant_tool_calls_rejected(self):
        row = DATA["records"][0]
        fake = sample_record(row)
        fake["messages"][0]["role"] = "tool"
        with self.assertRaisesRegex(SuiteError, "non-assistant"):
            check_run(row, fake)

    def test_reject_duplicate_json_keys(self):
        with self.assertRaisesRegex(SuiteError, "duplicate JSON"):
            _parse_json(b'{"suite":"banking","suite":"workspace"}')


if __name__ == "__main__":
    unittest.main()
