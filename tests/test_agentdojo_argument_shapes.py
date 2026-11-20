"""Fail-closed privacy and provenance tests for source-pinned argument shapes."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from agent_trace_lab.schema import SuiteError
from scripts.audit_agentdojo_argument_shapes import (
    OUTPUT, OUTPUT_CAP, MAX_FIELDS_PER_CALL, REDACTED_KEY,
    SAFE_NAMES, inventory_from_upstream, summarize_arguments, summarize_run,
    validate_inventory, report,
)
from scripts.audit_agentdojo_strata import _read_json_bounded

ROOT = Path(__file__).resolve().parents[1]
EXPOSURES = json.loads((ROOT / "docs/agentdojo_stratified_exposures.json").read_text("utf-8"))
INVENTORY = json.loads(OUTPUT.read_text("utf-8"))


class ArgumentShapesTests(unittest.TestCase):
    def test_exact_24_slot_source_hashes_actions_and_abstentions(self):
        validate_inventory(EXPOSURES, INVENTORY)
        self.assertEqual(len(INVENTORY["records"]), 24)
        self.assertEqual(sum(len(r["actions"]) for r in INVENTORY["records"]), 48)
        self.assertEqual(sum(r["status"] == "missing" for r in INVENTORY["records"]), 4)
        self.assertEqual(report(INVENTORY, False)["unknown_name_fields_redacted"], 4)
        self.assertTrue(all(r["human_authorization"] == "abstain"
                            and r["simulated_action_authorization"] == "abstain"
                            for r in INVENTORY["records"]))
        self.assertEqual(INVENTORY["accepted_independent_reviewers"], [])

    def test_unknown_argument_names_are_redacted_before_publication(self):
        value = summarize_arguments({
            "recipient": "person@example.com",
            "account-987654321@internal.net": {"secret": "hidden"},
            "api_key": "SECRET_SENTINEL",
            "amount": 9300000,
            "body": ["message text", "someone@example.org"],
        })
        self.assertEqual(len(value), 5)
        self.assertEqual(sum(f["name"] == REDACTED_KEY for f in value), 2)
        self.assertTrue(all(f["name"] in SAFE_NAMES | {REDACTED_KEY} for f in value))
        self.assertTrue({x["type"] for x in value} >= {"number", "object", "string", "array"})
        text = json.dumps(value)
        for secret in ("person@example.com", "internal.net", "SECRET_SENTINEL",
                       "9300000", "someone@example.org"):
            self.assertNotIn(secret, text)

    def test_coarse_json_type_detection(self):
        value = summarize_arguments({
            "recipient": None, "amount": 1.25, "subject": True,
            "body": ["secret"], "path": {"hidden": "value"}, "url": "https://example.org",
        })
        self.assertEqual({x["type"] for x in value},
                         {"null", "number", "boolean", "array", "object", "string"})

    def test_malformed_argument_objects_fail_closed(self):
        for args in (None, [], {"a": 1} | {f"x{i}": i for i in range(MAX_FIELDS_PER_CALL)}):
            with self.subTest(args_type=type(args).__name__):
                with self.assertRaises(SuiteError):
                    summarize_arguments(args)

    def test_self_authored_run_extraction_discards_every_raw_value(self):
        slot = {"suite": "banking", "task_index": 0, "condition": "baseline",
                "slot_index": 0}
        record = {
            "suite_name": "banking", "user_task_id": "user_task_0",
            "attack_type": None, "injection_task_id": None,
            "utility": True, "security": True,
            "messages": [{"role": "assistant", "tool_calls": [
                {"id": "call0", "function": "send_money",
                 "args": {"recipient": "SECRET_RECIPIENT", "amount": 999999,
                          "transaction account 123456": "private"}},
            ]}],
        }
        result = summarize_run(slot, json.dumps(record).encode("utf-8"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tool"], "send_money")
        self.assertEqual(result[0]["action_id"], "slot_00:action_000")
        text = json.dumps(result)
        self.assertNotIn("SECRET_RECIPIENT", text)
        self.assertNotIn("999999", text)
        self.assertNotIn("transaction account 123456", text)

    def test_one_pinned_run_can_be_fetched_and_checked_without_executing_actions(self):
        record = {
            "suite_name": "banking", "user_task_id": "user_task_0",
            "attack_type": None, "injection_task_id": None,
            "utility": True, "security": True,
            "messages": [{"role": "assistant", "tool_calls": [
                {"id": "id1", "function": "read_file", "args": {"file_path": "CONFIDENTIAL"}},
            ]}],
        }
        payload = json.dumps(record).encode("utf-8")
        original = {
            "status": "present", "suite": "banking", "task_index": 0,
            "condition": "baseline", "source_path": "immutable-path.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "observed_tools": ["read_file"],
        }
        with patch("scripts.audit_agentdojo_argument_shapes._fetch_limited",
                   return_value=("present", payload)) as fetched:
            records = inventory_from_upstream({"records": [original]})
            fetched.assert_called_once()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["actions"][0]["argument_shape"],
                         [{"name": "file_path", "type": "string"}])
        self.assertNotIn("CONFIDENTIAL", json.dumps(records))

    def test_changed_pinned_run_bytes_are_not_accepted(self):
        original = {
            "status": "present", "suite": "banking", "task_index": 0,
            "condition": "baseline", "source_path": "immutable-path.json",
            "sha256": "f" * 64, "observed_tools": ["read_file"],
        }
        with patch("scripts.audit_agentdojo_argument_shapes._fetch_limited",
                   return_value=("present", b'{"tampered": true}')):
            with self.assertRaisesRegex(SuiteError, "byte source differs"):
                inventory_from_upstream({"records": [original]})

    def test_missing_source_is_not_requested_or_replaced(self):
        manifest = {"records": [{
            "status": "missing", "suite": "slack", "task_index": 0,
            "condition": "direct", "source_path": "not-available.json",
            "sha256": None, "observed_tools": [],
        }]}
        with patch("scripts.audit_agentdojo_argument_shapes._fetch_limited") as fetch:
            result = inventory_from_upstream(manifest)
            fetch.assert_not_called()
        self.assertEqual(result[0]["actions"], [])
        self.assertEqual(result[0]["status"], "missing")

    def test_deny_fake_authorizations_and_modified_pinned_evidence(self):
        for field, value in (
            ("human_authorization", "allow"),
            ("simulated_action_authorization", "deny"),
            ("source_sha256", "0" * 64),
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(INVENTORY)
                mutated["records"][0][field] = value
                with self.assertRaises(SuiteError):
                    validate_inventory(EXPOSURES, mutated)

    def test_reject_arbitrary_published_fields_types_and_raw_values(self):
        for name, val in (
            ("name", "someone@private.example"), ("name", "api_key"),
            ("type", "SECRET_VALUE"), ("value", "bank_account_number"),
        ):
            with self.subTest(name=name, val=val):
                changed = copy.deepcopy(INVENTORY)
                item = changed["records"][0]["actions"][0]["argument_shape"][0]
                item[name] = val
                with self.assertRaises(SuiteError):
                    validate_inventory(EXPOSURES, changed)

    def test_cannot_drop_swap_or_fill_missing_slots(self):
        for change in ("drop", "swap", "populate_missing"):
            with self.subTest(change=change):
                result = copy.deepcopy(INVENTORY)
                if change == "drop":
                    result["records"].pop()
                elif change == "swap":
                    result["records"][0], result["records"][1] = result["records"][1], result["records"][0]
                else:
                    result["records"][7]["actions"] = [copy.deepcopy(result["records"][0]["actions"][0])]
                with self.assertRaises(SuiteError):
                    validate_inventory(EXPOSURES, result)

    def test_committed_inventory_contains_only_safe_metadata(self):
        raw = OUTPUT.read_text("utf-8")
        self.assertLess(len(raw.encode("utf-8")), OUTPUT_CAP)
        for secret in ('"args":', '"recipient_value":', '"message_content":',
                       '"publisher_utility":', "SECRET_SENTINEL", "CONFIDENTIAL",
                       "emma.johnson@", "UK123456789"):
            self.assertNotIn(secret, raw)
        self.assertFalse(report(INVENTORY, False)["actual_argument_values_stored"])
        self.assertEqual(report(INVENTORY, False)["accepted_independent_authorization_labels"], 0)

    def test_size_cap_is_enforced(self):
        with self.assertRaises(SuiteError):
            _read_json_bounded(OUTPUT, 1)


if __name__ == "__main__":
    unittest.main()
