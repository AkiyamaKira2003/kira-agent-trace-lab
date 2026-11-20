"""Negative controls for a synthetic-source annotation and consent abstention gate."""

import copy
import json
from pathlib import Path
from unittest import TestCase, mock

from scripts.verify_label_review import (
    infer_scenario_label, summary, validate_manifest, verify_upstream_case,
)


MANIFEST = json.loads(
    (Path(__file__).resolve().parents[1] / "docs" / "authorization_label_review.json").read_text(encoding="utf-8")
)


class LabelReviewTests(TestCase):
    def test_manifest_valid_and_all_human_grants_abstain(self):
        value = validate_manifest(copy.deepcopy(MANIFEST))
        report = summary(value, upstream_checked=False)
        self.assertEqual(report["scenario_counts"], {"allow": 1, "deny": 1})
        self.assertEqual(report["human_authorization_abstained"], 2)
        self.assertEqual(report["eligible_for_verified_authorization_metrics"], 0)

    def test_unsupported_mix_abstains_instead_of_inventing_binary_label(self):
        self.assertEqual(infer_scenario_label({
            "benign": 2, "injection_point": 1, "hijacked": 0, "failed_injection": 0,
        }), "abstain")

    def test_source_hash_rejects_corruption(self):
        case = copy.deepcopy(MANIFEST["cases"][0])
        case["source_sha256"] = "nonsense"
        candidate = copy.deepcopy(MANIFEST)
        candidate["cases"] = [case]
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_manifest(candidate)

    def test_label_must_follow_independent_author_step_annotations(self):
        candidate = copy.deepcopy(MANIFEST)
        candidate["cases"][1]["scenario_label"] = "allow"
        with self.assertRaisesRegex(ValueError, "conflicts"):
            validate_manifest(candidate)

    def test_synthetic_case_cannot_claim_consent_or_metrics(self):
        for key, value in (
            ("human_authorization_label", "allow"),
            ("human_authorization_evidence", "verified"),
            ("eligible_for_verified_authorization_metrics", True),
        ):
            with self.subTest(key=key):
                candidate = copy.deepcopy(MANIFEST)
                candidate["cases"][0][key] = value
                with self.assertRaisesRegex(ValueError, "cannot authenticate"):
                    validate_manifest(candidate)

    def test_unknown_source_path_rejected(self):
        candidate = copy.deepcopy(MANIFEST)
        candidate["cases"][0]["source_path"] = "../../private.json"
        with self.assertRaisesRegex(ValueError, "bounded pinned"):
            validate_manifest(candidate)

    def test_duplicate_case_rejected(self):
        candidate = copy.deepcopy(MANIFEST)
        candidate["cases"].append(copy.deepcopy(candidate["cases"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate case"):
            validate_manifest(candidate)

    def test_unrecognized_fields_rejected(self):
        candidate = copy.deepcopy(MANIFEST)
        candidate["cases"][0]["grants"] = [{"source_ref": "fabricated"}]
        with self.assertRaisesRegex(ValueError, "evidence fields"):
            validate_manifest(candidate)

    def test_upstream_hash_mismatch_fails_closed_before_parsing(self):
        class Fake:
            def __init__(self):
                self.status = 200

            def read(self, _):
                return b'{"id":"fabricated"}'

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        with mock.patch("scripts.verify_label_review.request.urlopen", return_value=Fake()):
            with self.assertRaisesRegex(ValueError, "digest"):
                verify_upstream_case(MANIFEST["cases"][0], MANIFEST["upstream_revision"])
