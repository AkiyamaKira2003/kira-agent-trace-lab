"""Negative controls for the exact pinned AgentDojo scenario, never consent."""

import copy
import json
from pathlib import Path
from unittest import TestCase

from scripts.verify_agentdojo_simulated_boundary import (
    report, validate_manifest, validate_record,
)


MANIFEST = json.loads(
    (Path(__file__).resolve().parents[1] / "docs" / "agentdojo_simulated_boundary.json").read_text(encoding="utf-8")
)


def fake_run(run):
    return {
        "suite_name": "workspace",
        "user_task_id": "user_task_0",
        "injection_task_id": run["injection_task_id"],
        "utility": run["benchmark_utility"],
        "security": run["benchmark_security_field"],
        "error": None,
        "messages": [
            {"role": "assistant", "tool_calls": [
                {"function": tool, "args": {}} for tool in run["observed_tools"]
            ]}
        ],
    }


class SimulatedBoundaryTests(TestCase):
    def test_valid_evidence_is_not_real_user_consent(self):
        value = validate_manifest(copy.deepcopy(MANIFEST))
        self.assertEqual(report(value, False)["human_authorization_abstentions"], 2)
        self.assertEqual(report(value, False)["authentic_human_grant_cases"], 0)

    def test_two_record_structures_reproduce_action_names(self):
        for run in MANIFEST["runs"]:
            with self.subTest(run=run["id"]):
                validate_record(run, fake_run(run), "user_task_0")

    def test_source_hash_tamper_rejected(self):
        doc = copy.deepcopy(MANIFEST)
        doc["runs"][0]["sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_manifest(doc)

    def test_attacker_tool_cannot_be_silently_removed(self):
        doc = copy.deepcopy(MANIFEST)
        doc["runs"][1]["observed_tools"].remove("send_email")
        with self.assertRaisesRegex(ValueError, "boundary"):
            validate_manifest(doc)

    def test_human_consent_claim_rejected(self):
        doc = copy.deepcopy(MANIFEST)
        doc["runs"][0]["human_authorization_label"] = "allow"
        with self.assertRaisesRegex(ValueError, "consent"):
            validate_manifest(doc)

    def test_pinned_source_path_cannot_be_replaced(self):
        doc = copy.deepcopy(MANIFEST)
        doc["runs"][0]["path"] = "../../secret.json"
        with self.assertRaisesRegex(ValueError, "boundary"):
            validate_manifest(doc)

    def test_missing_tools_rejected(self):
        run = MANIFEST["runs"][1]
        source = fake_run(run)
        source["messages"][0]["tool_calls"].pop()
        with self.assertRaisesRegex(ValueError, "sequence"):
            validate_record(run, source, "user_task_0")

    def test_mismatched_harness_security_rejected(self):
        run = MANIFEST["runs"][1]
        source = fake_run(run)
        source["security"] = False
        with self.assertRaisesRegex(ValueError, "outcomes"):
            validate_record(run, source, "user_task_0")

    def test_tool_arguments_must_remain_objects(self):
        run = MANIFEST["runs"][0]
        source = fake_run(run)
        source["messages"][0]["tool_calls"][0]["args"] = "untrusted text"
        with self.assertRaisesRegex(ValueError, "schema"):
            validate_record(run, source, "user_task_0")
