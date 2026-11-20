"""Fail-closed tests: packet privacy, pinned task sources and unverified reviewers."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from agent_trace_lab.schema import SuiteError
from scripts.agentdojo_review_packet import (
    audit_provisional_reviews, make_packet, validate_sources,
)
from scripts.audit_agentdojo_strata import validate_manifest, validate_spec


ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "docs/agentdojo_stratified_preregistration.json").read_text("utf-8"))
EXPOSURES = json.loads((ROOT / "docs/agentdojo_stratified_exposures.json").read_text("utf-8"))
SOURCES = json.loads((ROOT / "docs/agentdojo_task_sources.json").read_text("utf-8"))


class ReviewPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        validate_spec(SPEC)
        validate_manifest(SPEC, EXPOSURES)
        validate_sources(SOURCES)
        cls.packet = make_packet(EXPOSURES, SOURCES)
        cls.action = cls.packet["records"][0]["actions"][0]["action_id"]
        cls.sha = cls.packet["records"][0]["task_source_sha256"]

    def submission(self, labels=("within_scope", "within_scope")):
        reviewers = [
            {"reviewer_id": "reviewer_one", "identity_evidence_ref": "external-record-one"},
            {"reviewer_id": "reviewer_two", "identity_evidence_ref": "external-record-two"},
        ]
        return {
            "schema_version": "agentdojo-blinded-review-submission-1",
            "reviewers": reviewers,
            "reviews": [
                {"reviewer_id": reviewer["reviewer_id"], "action_id": self.action,
                 "label": label, "task_source_sha256": self.sha,
                 "task_source_span": "L20-L30",
                 "rationale": "This is a synthetic shape test, not a human review."}
                for reviewer, label in zip(reviewers, labels)
            ],
        }

    def test_sources_are_exactly_pinned_with_no_code_payload(self):
        self.assertEqual(len(SOURCES["sources"]), 4)
        self.assertEqual(SOURCES["source_revision"], EXPOSURES["source_revision"])
        self.assertEqual({item["suite"] for item in SOURCES["sources"]},
                         {"banking", "slack", "travel", "workspace"})
        self.assertNotIn("PROMPT", json.dumps(SOURCES))

    def test_tampered_sources_fail_closed(self):
        for key, bad in (("sha256", "a" * 64), ("size_bytes", 1),
                         ("task_classes_verified", ["UserTask1"])):
            with self.subTest(key=key):
                changed = copy.deepcopy(SOURCES)
                changed["sources"][0][key] = bad
                with self.assertRaises(SuiteError):
                    validate_sources(changed)

    def test_packet_preserves_all_missing_slots_and_actions(self):
        records = self.packet["records"]
        self.assertEqual(len(records), 24)
        self.assertEqual(sum(r["availability"] == "present" for r in records), 20)
        self.assertEqual(sum(r["availability"] == "missing" for r in records), 4)
        self.assertEqual(sum(len(r["actions"]) for r in records), 48)
        self.assertTrue(all(not r["actions"] and r["run_sha256"] is None
                            for r in records if r["availability"] == "missing"))
        self.assertEqual({r["review_status"] for r in records if r["availability"] == "missing"},
                         {"unavailable_no_review"})
        self.assertEqual({r["human_authorization"] for r in records}, {"abstain"})

    def test_packet_is_bounded_metadata_and_blinds_outcomes(self):
        value = json.dumps(self.packet)
        self.assertLess(len(value.encode("utf-8")), 35000)
        for secret_key in ("publisher_utility", "publisher_security", "arguments",
                           "recipients", "user_prompt", "email_body", "task_text"):
            self.assertNotIn('"' + secret_key + '"', value)
        self.assertFalse(self.packet["independent_reviewer_identity_verified"])

    def test_two_provisional_agreeing_reviews_are_never_certified(self):
        result = audit_provisional_reviews(self.packet, self.submission())
        self.assertEqual(result["paired_action_reviews"], 1)
        self.assertEqual(result["provisional_nonabstain_agreement"], 1)
        self.assertEqual(result["accepted_independent_agreements"], 0)
        self.assertFalse(result["independent_reviewer_identity_verified"])
        self.assertIsNone(result["population_safety_accuracy"])
        self.assertEqual(result["unavailable_exposure_slots"], 4)

    def test_disagreement_requires_independent_adjudication(self):
        result = audit_provisional_reviews(self.packet, self.submission(
            ("within_scope", "out_of_scope")))
        self.assertEqual(result["provisional_disagreement_needs_adjudication"], 1)
        self.assertEqual(result["provisional_nonabstain_agreement"], 0)
        self.assertEqual(result["accepted_independent_agreements"], 0)

    def test_abstention_does_not_count_as_nonabstain_agreement(self):
        for labels in (("abstain", "abstain"), ("abstain", "within_scope")):
            with self.subTest(labels=labels):
                result = audit_provisional_reviews(self.packet, self.submission(labels))
                self.assertEqual(result["pairs_with_abstentions"], 1)
                self.assertEqual(result["provisional_nonabstain_agreement"], 0)

    def test_only_one_reviewer_is_insufficient(self):
        value = self.submission()
        value["reviewers"].pop()
        with self.assertRaisesRegex(SuiteError, "two distinct"):
            audit_provisional_reviews(self.packet, value)

    def test_same_reviewer_cannot_impersonate_two_participants(self):
        value = self.submission()
        value["reviewers"][1]["reviewer_id"] = "reviewer_one"
        with self.assertRaisesRegex(SuiteError, "duplicate reviewer"):
            audit_provisional_reviews(self.packet, value)

    def test_duplicate_action_review_rejected(self):
        value = self.submission()
        value["reviews"].append(copy.deepcopy(value["reviews"][0]))
        with self.assertRaisesRegex(SuiteError, "duplicate reviewer action"):
            audit_provisional_reviews(self.packet, value)

    def test_missing_exposure_cannot_be_labelled(self):
        value = self.submission()
        value["reviews"][0]["action_id"] = "slot_07:action_000"
        with self.assertRaisesRegex(SuiteError, "unknown reviewer/action"):
            audit_provisional_reviews(self.packet, value)

    def test_wrong_source_hash_is_not_valid_review(self):
        value = self.submission()
        value["reviews"][1]["task_source_sha256"] = "e" * 64
        with self.assertRaisesRegex(SuiteError, "source-bound rationale"):
            audit_provisional_reviews(self.packet, value)

    def test_source_span_and_rationale_are_required(self):
        for field, invalid in (("task_source_span", "not-a-source-span"),
                               ("rationale", ""), ("rationale", 5)):
            with self.subTest(field=field):
                value = self.submission()
                value["reviews"][0][field] = invalid
                with self.assertRaises(SuiteError):
                    audit_provisional_reviews(self.packet, value)

    def test_invalid_label_types_fail_closed(self):
        for invalid in ([], None, "grant_allow"):
            with self.subTest(invalid=invalid):
                value = self.submission()
                value["reviews"][0]["label"] = invalid
                with self.assertRaisesRegex(SuiteError, "invalid label"):
                    audit_provisional_reviews(self.packet, value)

    def test_empty_submission_is_not_real_review(self):
        value = self.submission()
        value["reviews"] = []
        result = audit_provisional_reviews(self.packet, value)
        self.assertEqual(result["paired_action_reviews"], 0)
        self.assertEqual(result["accepted_independent_agreements"], 0)


if __name__ == "__main__":
    unittest.main()
