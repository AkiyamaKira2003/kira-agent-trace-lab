"""Fail-closed checks for a bounded, opt-in Hugging Face provenance audit."""

import unittest

from scripts.audit_hf_preview_revision import (
    canonical_bytes,
    validate_preview,
    validate_source_metadata,
)


REV = "4fa4c2ae9afc6b397bc50391d43450c79993c138"
ROW = {"messages": [{"role": "assistant", "tool_calls": []}], "license": "Apache-2.0"}


class PreviewAuditTest(unittest.TestCase):
    def sample(self):
        return {"rows": [{"row_idx": 0, "truncated_cells": [], "row": ROW}]}

    def test_matching_revision_and_row(self):
        value = validate_preview(self.sample(), REV, REV, ROW)
        self.assertEqual(value["bytes"], str(len(canonical_bytes(ROW))))
        self.assertEqual(value["source_repo_license"], "Apache-2.0")

    def test_missing_or_mismatched_revision_rejected(self):
        for header in (None, "abc", "0" * 40):
            with self.subTest(header=header), self.assertRaisesRegex(ValueError, "X-Revision"):
                validate_preview(self.sample(), header, REV, ROW)

    def test_truncation_rejected(self):
        data = self.sample()
        data["rows"][0]["truncated_cells"] = ["messages"]
        with self.assertRaisesRegex(ValueError, "truncated"):
            validate_preview(data, REV, REV, ROW)

    def test_missing_and_reordered_first_row_rejected(self):
        for data in ({"rows": []}, {"rows": [{"row_idx": 2, "truncated_cells": [], "row": ROW}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_preview(data, REV, REV, ROW)

    def test_changed_contents_rejected(self):
        modified = {"messages": [], "license": "Apache-2.0"}
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_preview(self.sample(), REV, REV, modified)

    def test_metadata_commit_or_license_mismatch_rejected(self):
        validate_source_metadata({"sha": REV, "cardData": {"license": "cc-by-4.0"}}, REV)
        for meta in (
            {"sha": "0" * 40, "cardData": {"license": "cc-by-4.0"}},
            {"sha": REV, "cardData": {"license": "unknown"}},
            {"sha": REV},
        ):
            with self.subTest(meta=meta), self.assertRaises(ValueError):
                validate_source_metadata(meta, REV)


if __name__ == "__main__":
    unittest.main()
