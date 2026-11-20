"""ATL-004AN: honest, self-contained, offline static demo contract."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from pathlib import Path
import unittest

from agent_trace_lab.engine import compare_policies
from agent_trace_lab.schema import load_json_document, load_suite


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "policy-contrast-research-demo.html"
BASE = ROOT / "examples" / "demo_permissive.json"
CANDIDATE = ROOT / "examples" / "compare_candidate_task_guarded.json"


class DemoReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.data_values: dict[str, int] = {}
        self.data_labels: dict[str, str] = {}
        self.active_key: str | None = None
        self.external_assets = []
        self.forbidden_tags = []
        self.tags = []
        self.links = []
        self.progress = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append(tag)
        if tag in {"script", "iframe", "object", "embed", "form", "video", "audio"}:
            self.forbidden_tags.append(tag)
        if any(name.lower().startswith("on") for name in attributes):
            self.external_assets.append(f"{tag}:event-handler")
        for name in ("src", "srcset", "action"):
            if name in attributes:
                self.external_assets.append(f"{tag}:{name}")
        if tag == "a":
            self.links.append(attributes.get("href", ""))
        if tag == "data":
            key = attributes.get("data-key")
            if key in self.data_values or not key or not attributes.get("value", "").isdigit():
                raise ValueError("invalid or duplicate counted metric")
            self.data_values[key] = int(attributes["value"])
            self.data_labels[key] = ""
            self.active_key = key
        if tag == "progress":
            self.progress.append((attributes.get("value"), attributes.get("max")))

    def handle_data(self, data):
        if self.active_key is not None:
            self.data_labels[self.active_key] += data

    def handle_endtag(self, tag):
        if tag == "data":
            self.active_key = None


class OfflineResearchDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markup = DEMO.read_text(encoding="utf-8")
        cls.parsed = DemoReader()
        cls.parsed.feed(cls.markup)

    def test_all_six_visible_counts_match_live_comparison_engine(self):
        actual = compare_policies(
            load_suite(BASE), load_json_document(CANDIDATE),
        )["summary"]
        self.assertEqual(self.parsed.data_values, actual)
        for key, count in actual.items():
            self.assertEqual(self.parsed.data_labels[key].strip(), str(count))
        self.assertEqual(self.parsed.progress, [
            (str(actual["changed"]), str(actual["total_cases"])),
        ])

    def test_no_unsafe_active_content_or_network_dependencies(self):
        self.assertEqual(self.parsed.forbidden_tags, [])
        self.assertEqual(self.parsed.external_assets, [])
        self.assertNotRegex(self.markup.lower(), r"@import|url\s*\(|<meta[^>]+http-equiv\s*=\s*['\"]?refresh")
        self.assertNotRegex(self.markup, r"https?://|www\.")
        self.assertNotIn("fetch(", self.markup)
        self.assertTrue(self.markup.lstrip().lower().startswith("<!doctype html>"))

    def test_no_raw_private_trace_content_or_case_tool_identifiers(self):
        original = load_suite(BASE)
        for case in original["cases"]:
            self.assertNotIn(case["id"], self.markup)
            for trace in case["trace"]:
                self.assertNotIn(trace["tool"], self.markup)
                for arg in trace["arguments"].values():
                    if isinstance(arg, str):
                        self.assertNotIn(arg, self.markup)
        for forbidden in ("unrequested@example.invalid", "synthetic_message_01",
                          "TASK_GRANT_REQUIRED", "PRIVATE_SYNTHETIC"):
            self.assertNotIn(forbidden, self.markup)

    def test_explicit_disclosures_are_visible_in_text_not_hidden_metadata(self):
        visible = " ".join(self.markup.split())
        for notice in (
            "Synthetic-only evidence",
            "not a prompt-injection detector",
            "not an authenticated record",
            "No tool actions are executed",
            "not an external security dataset",
            "not an independently proven authorization verdict",
        ):
            self.assertIn(notice, visible)
        self.assertIn("lang=\"en\"", self.markup)
        self.assertIn('name="viewport"', self.markup)

    def test_keyboard_readable_semantics_and_local_links(self):
        for tag in ("main", "header", "section", "article", "h1", "h2",
                    "dl", "dt", "dd", "progress", "label", "footer"):
            self.assertIn(tag, self.parsed.tags)
        self.assertIn('for="changes"', self.markup)
        self.assertIn('id="changes"', self.markup)
        self.assertIn(":focus-visible", self.markup)
        self.assertEqual(self.parsed.links, ["../README.md"])
        for url in self.parsed.links:
            self.assertFalse(url.startswith(("http:", "https:", "//", "javascript:", "data:")))
            resolved = (DEMO.parent / url).resolve()
            self.assertTrue(resolved.is_relative_to(ROOT.resolve()))
            self.assertTrue(resolved.is_file())

    def test_layout_has_mobile_single_column_fallback(self):
        self.assertRegex(self.markup, r"@media\s*\(max-width:\s*650px\)")
        self.assertIn("grid-template-columns: 1fr;", self.markup)
        self.assertRegex(self.markup, r"max-width:\s*980px")
        self.assertNotRegex(self.markup, r"position:\s*fixed")


if __name__ == "__main__":
    unittest.main()
