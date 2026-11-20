"""Structural, privacy and negative controls for the task-intent feasibility matrix."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from agent_trace_lab.schema import SuiteError
from scripts.audit_agentdojo_task_scope import (
    SOURCE_AUDIT, MATRIX_CAP, MATRIX_PATH, _reference_calls,
    build_matrix, report, validate_matrix, audit_pinned_source_ast,
)
from scripts.audit_agentdojo_strata import _read_json_bounded

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "docs/agentdojo_stratified_preregistration.json").read_text("utf-8"))
EXPOSURES = json.loads((ROOT / "docs/agentdojo_stratified_exposures.json").read_text("utf-8"))
SOURCES = json.loads((ROOT / "docs/agentdojo_task_sources.json").read_text("utf-8"))
MATRIX = json.loads(MATRIX_PATH.read_text("utf-8"))


class TaskScopeTests(unittest.TestCase):
    def test_matrix_is_frozen_to_source_and_original_exposures(self):
        self.assertEqual(validate_matrix(SPEC, EXPOSURES, SOURCES, MATRIX), MATRIX)
        self.assertEqual(build_matrix(SPEC, EXPOSURES, SOURCES), MATRIX)
        self.assertEqual(len(MATRIX["tasks"]), 8)
        self.assertEqual(len(MATRIX["slots"]), 24)
        self.assertEqual(report(MATRIX, 0)["source_task_definitions_checked_online"], 0)

    def test_missing_slots_remain_missing_not_zero_call_logs(self):
        absent = [x for x in MATRIX["slots"] if x["availability"] == "missing"]
        self.assertEqual(len(absent), 4)
        self.assertEqual({(x["suite"], x["task_id"], x["condition"]) for x in absent}, {
            ("slack", "user_task_0", "direct"),
            ("slack", "user_task_0", "important_instructions"),
            ("slack", "user_task_1", "direct"),
            ("slack", "user_task_1", "important_instructions"),
        })
        self.assertTrue(all(x["observed_action_count"] is None
                            and x["nonreference_tool_name_count"] is None for x in absent))

    def test_actions_are_only_tool_name_overlap_not_security_verdicts(self):
        rows = MATRIX["slots"]
        self.assertEqual(sum(x["observed_action_count"] or 0 for x in rows), 48)
        self.assertEqual(sum(x["nonreference_tool_name_count"] or 0 for x in rows), 11)
        self.assertTrue(all(x["simulated_action_authorization"] == "abstain"
                            and x["human_authorization"] == "abstain"
                            and not x["arguments_and_targets_reviewed"] for x in rows))
        self.assertEqual(MATRIX["independent_reviewers"], [])

    def test_reference_calls_are_not_user_grants(self):
        self.assertTrue(all(not x["reference_tools_are_authorization"]
                            and not x["recorded_arguments_inspected"]
                            and x["simulated_action_authorization"] == "abstain"
                            and x["human_authorization"] == "abstain"
                            and x["independent_review_status"] == "not_reviewed"
                            for x in MATRIX["tasks"]))

    def test_important_task_intents_are_distinct(self):
        pairs = {(x["suite"], x["task_id"]): x for x in MATRIX["tasks"]}
        self.assertEqual(pairs["travel", "user_task_0"]["intended_effect"], "hotel_reservation")
        self.assertEqual(pairs["travel", "user_task_0"]["condition_scope"], "rating_above_four")
        self.assertEqual(pairs["travel", "user_task_1"]["intended_effect"],
                         "calendar_event_not_reservation")
        self.assertNotIn("reserve_hotel",
                         pairs["travel", "user_task_1"]["benchmark_reference_tools"])
        self.assertEqual(pairs["slack", "user_task_1"]["intended_effect"], "direct_message")
        self.assertEqual(pairs["banking", "user_task_0"]["intended_effect"], "payment")
        for suite, index in (("banking", 1), ("slack", 0), ("workspace", 0), ("workspace", 1)):
            self.assertEqual(pairs[suite, f"user_task_{index}"]["intended_effect"], "read_only")

    def test_cannot_claim_grants_or_independent_review_by_editing_matrix(self):
        modifications = [
            ("tasks", 0, "human_authorization", "allow"),
            ("tasks", 0, "simulated_action_authorization", "deny"),
            ("tasks", 1, "reference_tools_are_authorization", True),
            ("tasks", 1, "independent_review_status", "verified"),
            ("slots", 0, "human_authorization", "deny"),
            ("slots", 0, "arguments_and_targets_reviewed", True),
        ]
        for group, index, key, value in modifications:
            with self.subTest(field=key, value=value):
                edited = copy.deepcopy(MATRIX)
                edited[group][index][key] = value
                with self.assertRaises(SuiteError):
                    validate_matrix(SPEC, EXPOSURES, SOURCES, edited)

    def test_cannot_guess_unrequested_reservation_or_expand_ground_truth(self):
        for field, value in (
            ("intended_effect", "hotel_reservation"),
            ("condition_scope", "unconditional_reservation"),
            ("benchmark_reference_tools", ["reserve_hotel"]),
        ):
            with self.subTest(field=field):
                edited = copy.deepcopy(MATRIX)
                task = next(x for x in edited["tasks"]
                            if x["suite"] == "travel" and x["task_id"] == "user_task_1")
                task[field] = value
                with self.assertRaises(SuiteError):
                    validate_matrix(SPEC, EXPOSURES, SOURCES, edited)

    def test_cannot_remove_reorder_replace_or_fill_missing_source_slots(self):
        for variant in ("drop", "swap", "mark_present", "fabricate_calls"):
            with self.subTest(variant=variant):
                edited = copy.deepcopy(MATRIX)
                if variant == "drop":
                    edited["slots"].pop()
                elif variant == "swap":
                    edited["slots"][0], edited["slots"][1] = edited["slots"][1], edited["slots"][0]
                elif variant == "mark_present":
                    edited["slots"][7]["availability"] = "present"
                else:
                    edited["slots"][7]["observed_action_count"] = 0
                with self.assertRaises(SuiteError):
                    validate_matrix(SPEC, EXPOSURES, SOURCES, edited)

    def test_no_raw_task_code_or_arguments_published(self):
        raw = MATRIX_PATH.read_text("utf-8")
        self.assertLess(len(raw.encode("utf-8")), MATRIX_CAP)
        for key in ('"PROMPT":', '"model_output":', '"recipient":', "bill-december-2023",
                    "utility_field", "source_error_present", '"args"', '"messages"'):
            self.assertNotIn(key, raw)
        self.assertNotIn("emma.johnson@", raw)

    def test_metadata_size_cap_enforced(self):
        with self.assertRaises(SuiteError):
            _read_json_bounded(MATRIX_PATH, 1)

    def test_reference_function_names_read_without_executing_ast(self):
        program = ast.parse('def ground_truth():\n  return [FunctionCall(function="read_file",args={}), FunctionCall(function="send_money",args={})]\n')
        self.assertEqual(_reference_calls(program.body[0]), ["read_file", "send_money"])
        unsafe = ast.parse('def ground_truth():\n  return FunctionCall(function=variable,args={})\n')
        with self.assertRaises(SuiteError):
            _reference_calls(unsafe.body[0])

    def test_pinned_source_ast_rejects_modified_classes_without_code_execution(self):
        from scripts.audit_agentdojo_task_scope import fetch_pinned_source
        fake = b"class UserTask0:\n PROMPT='hey'\n\nclass UserTask1:\n PROMPT='hi'\n"
        with patch("scripts.audit_agentdojo_task_scope.fetch_pinned_source", return_value=fake):
            with self.assertRaises(SuiteError):
                audit_pinned_source_ast(SOURCES)

    def test_wrong_source_revision_hash_rejected(self):
        edited = copy.deepcopy(SOURCES)
        edited["sources"][0]["sha256"] = "0" * 64
        with self.assertRaises(SuiteError):
            build_matrix(SPEC, EXPOSURES, edited)


if __name__ == "__main__":
    unittest.main()
