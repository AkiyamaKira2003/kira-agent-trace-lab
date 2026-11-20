"""No-network proof tests: source bytes, span boundaries and reviewer abstention."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from agent_trace_lab.schema import SuiteError
from scripts.agentdojo_span_provenance import (
    SOURCE_CAP, cite_span_digest, fetch_pinned_source, parse_line_ranges,
    prevalidate_citation_submission, validate_citation_proofs,
)
from scripts.agentdojo_review_packet import make_packet

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "docs/agentdojo_stratified_exposures.json").read_text("utf-8"))
SOURCES = json.loads((ROOT / "docs/agentdojo_task_sources.json").read_text("utf-8"))


class SpanProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.packet = make_packet(MANIFEST, SOURCES)
        self.fake_source = b"class UserTask0:\n    PROMPT = 'synthetic'\nclass UserTask1:\n    PROMPT = 'synthetic'\n"
        self.fake_sha = hashlib.sha256(self.fake_source).hexdigest()
        self.packet["records"][0]["task_source_sha256"] = self.fake_sha
        self.first_action = self.packet["records"][0]["actions"][0]["action_id"]
        self.citation = "L1-L2,L4"

    def submission(self, labels=("within_scope", "within_scope")):
        digest = cite_span_digest(self.fake_source, self.citation)
        return {
            "schema_version": "agentdojo-citation-review-submission-2",
            "reviewers": [
                {"reviewer_id": "person_one", "identity_evidence_ref": "fictional-one"},
                {"reviewer_id": "person_two", "identity_evidence_ref": "fictional-two"},
            ],
            "reviews": [
                {"reviewer_id": r, "action_id": self.first_action, "label": labels[i],
                 "task_source_sha256": self.fake_sha, "task_source_span": self.citation,
                 "task_source_span_digest": digest,
                 "rationale": "This synthetic test is not an actual independent review."}
                for i, r in enumerate(("person_one", "person_two"))
            ],
        }

    def test_disjoint_spans_are_normalized(self):
        self.assertEqual(parse_line_ranges("L1-L2,L4,L7-L8"), [(1, 2), (4, 4), (7, 8)])

    def test_invalid_overlap_reordering_oversize_and_syntax_fail(self):
        for value in (
            "", "L0", "L01", "L3-L2", "L1-L13", "L1-L2,L2-L3",
            "L4,L3", "L1,L1", "L1,L1-L4", "L1, L4",
            "L1,L3,L5,L7,L9", "L1-L12,L13-L25", "L1-L12,L13-L24,L26",
            "L9999999", None, 33,
        ):
            with self.subTest(span=value):
                with self.assertRaises(SuiteError):
                    parse_line_ranges(value)

    def test_source_line_bounds_and_file_cap(self):
        with self.assertRaisesRegex(SuiteError, "outside"):
            cite_span_digest(self.fake_source, "L99")
        with self.assertRaisesRegex(SuiteError, "oversized"):
            cite_span_digest(b"x" * (SOURCE_CAP + 1), "L1")
        with self.assertRaisesRegex(SuiteError, "missing"):
            cite_span_digest(b"", "L1")

    def test_proof_binds_selected_lines_and_line_numbers(self):
        proof = cite_span_digest(self.fake_source, self.citation)
        self.assertEqual(proof, cite_span_digest(self.fake_source, self.citation))
        self.assertNotEqual(proof, cite_span_digest(self.fake_source, "L2-L3"))
        self.assertNotEqual(proof, cite_span_digest(self.fake_source + b"x\n", "L2-L3"))
        changed = self.fake_source.replace(b"synthetic", b"altered!")
        self.assertNotEqual(proof, cite_span_digest(changed, self.citation))

    def test_verified_bytes_still_do_not_verify_human_reviewers(self):
        result = validate_citation_proofs(self.packet, self.submission(),
                                          {"banking": self.fake_source})
        self.assertEqual(result["cited_source_byte_proofs_verified"], 2)
        self.assertEqual(result["provisional_nonabstain_agreement"], 1)
        self.assertEqual(result["accepted_independent_agreements"], 0)
        self.assertFalse(result["source_span_meaning_verified"])
        self.assertFalse(result["independent_reviewer_identity_verified"])

    def test_wrong_digest_rejected_even_when_source_sha_matches(self):
        value = self.submission()
        value["reviews"][0]["task_source_span_digest"] = "e" * 64
        with self.assertRaisesRegex(SuiteError, "digest disagree"):
            validate_citation_proofs(self.packet, value, {"banking": self.fake_source})

    def test_wrong_pinned_source_rejected_even_when_span_digest_matches(self):
        with self.assertRaisesRegex(SuiteError, "digest disagree"):
            validate_citation_proofs(self.packet, self.submission(),
                                     {"banking": self.fake_source + b"x"})

    def test_missing_source_bytes_fail_closed(self):
        with self.assertRaisesRegex(SuiteError, "digest disagree"):
            validate_citation_proofs(self.packet, self.submission(), {})

    def test_missing_or_extra_span_evidence_is_rejected(self):
        for operation in ("drop", "extra", "wrong_version", "unknown_action"):
            with self.subTest(operation=operation):
                value = self.submission()
                if operation == "drop":
                    del value["reviews"][0]["task_source_span_digest"]
                elif operation == "extra":
                    value["reviews"][0]["untrusted"] = "forged"
                elif operation == "wrong_version":
                    value["schema_version"] = "agentdojo-blinded-review-submission-1"
                else:
                    value["reviews"][0]["action_id"] = "slot_07:action_000"
                with self.assertRaises(SuiteError):
                    prevalidate_citation_submission(self.packet, value)

    def test_overlapping_and_oversize_spans_fail_before_network(self):
        for invalid in ("L1-L3,L3-L5", "L1-L15", "L200,L199"):
            with self.subTest(invalid=invalid):
                value = self.submission()
                value["reviews"][0]["task_source_span"] = invalid
                with self.assertRaises(SuiteError):
                    prevalidate_citation_submission(self.packet, value)

    def test_malformed_hash_and_reviewers_fail_before_network(self):
        for change in ("bad_digest", "one_person", "same_name"):
            with self.subTest(change=change):
                value = self.submission()
                if change == "bad_digest":
                    value["reviews"][0]["task_source_span_digest"] = "broken"
                elif change == "one_person":
                    value["reviewers"].pop()
                else:
                    value["reviewers"][1]["reviewer_id"] = "person_one"
                with self.assertRaises(SuiteError):
                    prevalidate_citation_submission(self.packet, value)

    def test_empty_reviews_certify_nothing(self):
        value = self.submission()
        value["reviews"] = []
        result = validate_citation_proofs(self.packet, value, {})
        self.assertEqual(result["cited_source_byte_proofs_verified"], 0)
        self.assertEqual(result["accepted_independent_agreements"], 0)

    def test_pinned_source_fetch_rejects_byte_hash_or_size_tampering(self):
        data = self.fake_source
        entry = {"path": "src/agentdojo/default_suites/v1/banking/user_tasks.py",
                 "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            def read(self, _: int): return data
        with patch("scripts.agentdojo_span_provenance.request.urlopen",
                   return_value=Response()):
            self.assertEqual(fetch_pinned_source(entry), data)
            bad = {**entry, "size_bytes": 5}
            with self.assertRaisesRegex(SuiteError, "source pin mismatch"):
                fetch_pinned_source(bad)
            bad = {**entry, "sha256": "f" * 64}
            with self.assertRaisesRegex(SuiteError, "source pin mismatch"):
                fetch_pinned_source(bad)


if __name__ == "__main__":
    unittest.main()
