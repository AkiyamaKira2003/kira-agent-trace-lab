"""Offline synthetic batch-manifest negative controls; no network or real traces."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_trace_lab.otlp import import_otlp
from agent_trace_lab.schema import SuiteError, load_json_document, load_suite
from scripts.verify_otlp_capture_manifest import assemble_declared_capture

ROOT = Path(__file__).resolve().parents[1]
POLICY = load_suite(ROOT / "examples" / "suite.json")["policy"]


class OtlpCaptureManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        document = load_json_document(ROOT / "examples" / "otlp_spans.json")
        left = copy.deepcopy(document)
        right = copy.deepcopy(document)
        left["resourceSpans"][0]["scopeSpans"][0]["spans"] = (
            left["resourceSpans"][0]["scopeSpans"][0]["spans"][:2]
        )
        right["resourceSpans"][0]["scopeSpans"][0]["spans"] = (
            right["resourceSpans"][0]["scopeSpans"][0]["spans"][2:]
        )
        self.documents = [left, right]
        self.manifest = {"expected_batch_count": 2, "batches": []}
        for i, item in enumerate(self.documents, 1):
            raw = json.dumps(item, sort_keys=True).encode("utf-8")
            (self.directory / f"http-post-{i}.json").write_bytes(raw)
            self.manifest["batches"].append({
                "index": i, "sha256": hashlib.sha256(raw).hexdigest(),
            })

    def convert(self, manifest=None):
        assembled = assemble_declared_capture(
            self.directory, self.manifest if manifest is None else manifest,
        )
        return import_otlp(assembled, policy=POLICY, case_id="declared", expected="deny")

    def test_original_two_files_assemble_without_fabricating_human_grants(self):
        suite = self.convert()
        self.assertEqual([row["tool"] for row in suite["cases"][0]["trace"]],
                         ["files.read", "docs.search"])
        self.assertEqual(suite["cases"][0]["expected"], "deny")
        self.assertNotIn("task_authorization", suite["cases"][0])

    def test_missing_and_extra_post_fail_before_assembly(self):
        (self.directory / "http-post-2.json").unlink()
        with self.assertRaises(SuiteError):
            self.convert()
        (self.directory / "http-post-2.json").write_bytes(
            json.dumps(self.documents[1], sort_keys=True).encode("utf-8"))
        (self.directory / "http-post-3.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(SuiteError):
            self.convert()

    def test_duplicate_or_gapped_batch_indexes_fail(self):
        for indexes in ([1, 1], [2, 3], [1, 3], [2, 1], [1, True]):
            with self.subTest(indexes=indexes):
                changed = copy.deepcopy(self.manifest)
                for batch, index in zip(changed["batches"], indexes):
                    batch["index"] = index
                with self.assertRaises(SuiteError):
                    self.convert(changed)

    def test_manifest_count_bounds_and_unexpected_keys_fail(self):
        variants = (
            {"expected_batch_count": 1, "batches": self.manifest["batches"]},
            {"expected_batch_count": 9, "batches": self.manifest["batches"]},
            {"expected_batch_count": "2", "batches": self.manifest["batches"]},
            {"expected_batch_count": True, "batches": self.manifest["batches"]},
            {"expected_batch_count": 2, "batches": self.manifest["batches"], "complete": True},
            {"expected_batch_count": 2, "batches": [self.manifest["batches"][0]]},
        )
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(SuiteError):
                    self.convert(variant)

    def test_tampered_bytes_and_malformed_digest_fail(self):
        file = self.directory / "http-post-2.json"
        file.write_bytes(file.read_bytes() + b" ")
        with self.assertRaises(SuiteError):
            self.convert()
        changed = copy.deepcopy(self.manifest)
        changed["batches"][1]["sha256"] = "a" * 63
        with self.assertRaises(SuiteError):
            self.convert(changed)

    def test_oversized_file_even_with_matching_digest_fails(self):
        raw = b" " * (512 * 1024 + 1)
        (self.directory / "http-post-1.json").write_bytes(raw)
        changed = copy.deepcopy(self.manifest)
        changed["batches"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(SuiteError, "byte limit"):
            self.convert(changed)

    def test_unexpected_http_post_filename_is_rejected(self):
        (self.directory / "http-post-3.tmp").write_text("synthetic", encoding="utf-8")
        with self.assertRaisesRegex(SuiteError, "inventory"):
            self.convert()

    def test_duplicate_replayed_payload_digests_fail(self):
        original = (self.directory / "http-post-1.json").read_bytes()
        (self.directory / "http-post-2.json").write_bytes(original)
        changed = copy.deepcopy(self.manifest)
        changed["batches"][1]["sha256"] = hashlib.sha256(original).hexdigest()
        with self.assertRaises(SuiteError):
            self.convert(changed)

    def test_mixed_trace_ids_including_parent_are_rejected(self):
        doc = copy.deepcopy(self.documents[0])
        doc["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"] = "f" * 32
        doc["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["spanId"] = "e" * 16
        raw = json.dumps(doc, sort_keys=True).encode("utf-8")
        (self.directory / "http-post-1.json").write_bytes(raw)
        changed = copy.deepcopy(self.manifest)
        changed["batches"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(SuiteError):
            self.convert(changed)

    def test_duplicate_span_ids_across_batches_rejected(self):
        doc = copy.deepcopy(self.documents[1])
        doc["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["spanId"] = (
            self.documents[0]["resourceSpans"][0]["scopeSpans"][0]["spans"][1]["spanId"]
        )
        raw = json.dumps(doc, sort_keys=True).encode("utf-8")
        (self.directory / "http-post-2.json").write_bytes(raw)
        changed = copy.deepcopy(self.manifest)
        changed["batches"][1]["sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(SuiteError):
            self.convert(changed)

    def test_private_marker_and_duplicate_json_keys_fail_without_cli_output(self):
        marker = "SYNTHETIC_PRIVATE_MANIFEST_MARKER_87245"
        # Syntactically valid JSON with a repeated key; no private content is
        # allowed in the CLI's bounded failure output.
        raw = ('{"resourceSpans":[],"resourceSpans":[],"' + marker + '":0}').encode("utf-8")
        (self.directory / "http-post-1.json").write_bytes(raw)
        self.manifest["batches"][0]["sha256"] = hashlib.sha256(raw).hexdigest()
        manifest_path = self.directory / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        process = subprocess.run([
            sys.executable, "-m", "scripts.verify_otlp_capture_manifest",
            "--capture-dir", str(self.directory), "--manifest", str(manifest_path),
            "--policy-suite", str(ROOT / "examples" / "suite.json"),
            "--case-id", "synthetic", "--expected", "deny",
        ], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(process.returncode, 2)
        self.assertNotIn(marker, process.stdout + process.stderr)
        self.assertNotIn("Traceback", process.stdout + process.stderr)

    def test_self_declared_manifest_does_not_authenticate_trace_end(self):
        # An omitted *future* batch not declared by the author cannot be
        # detected; success on these two files is only a local integrity fact.
        self.assertEqual(len(self.convert()["cases"][0]["trace"]), 2)

    def test_cli_success_is_counts_only_with_truthful_security_nonclaims(self):
        manifest_path = self.directory / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        result = subprocess.run([
            sys.executable, "-m", "scripts.verify_otlp_capture_manifest",
            "--capture-dir", str(self.directory), "--manifest", str(manifest_path),
            "--policy-suite", str(ROOT / "examples" / "suite.json"),
            "--case-id", "local_synthetic", "--expected", "deny",
        ], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["declared_batch_count"], 2)
        self.assertEqual(summary["recorded_tool_call_count"], 2)
        self.assertFalse(summary["end_of_trace_authenticated"])
        self.assertFalse(summary["user_authorization_authenticated"])
        self.assertFalse(summary["recorded_actions_executed"])
        self.assertNotIn("synthetic/readme.txt", result.stdout)


if __name__ == "__main__":
    unittest.main()
