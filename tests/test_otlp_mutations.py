"""Deterministic synthetic mutation checks for the narrow OTLP JSON importer.

These are adversarial parser regressions, not a general-purpose fuzzer or a
claim about security of live agents. No recorded user traces or tools run.
"""

from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_trace_lab.otlp import import_otlp
from agent_trace_lab.schema import SuiteError, load_json_document, load_suite

ROOT = Path(__file__).resolve().parents[1]
SEED = 0x004D6
PRIVATE_MARKER = "SYNTHETIC_PRIVATE_MUTATION_004DG_DO_NOT_LOG"


def _tool_span(export: dict) -> dict:
    return export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]


def _args_attribute(export: dict) -> dict:
    return _tool_span(export)["attributes"][2]


def _replace(export: dict, path: tuple, value: object) -> None:
    node = export
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


class OtlpMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = load_json_document(ROOT / "examples" / "otlp_spans.json")
        cls.policy = load_suite(ROOT / "examples" / "suite.json")["policy"]

    def _import(self, export: dict) -> dict:
        return import_otlp(export, policy=self.policy, case_id="synthetic_mutation", expected="allow")

    def test_seeded_malformed_inputs_fail_closed_without_echoing_content(self) -> None:
        """Every mutation is a distinct invalid object at a supported boundary."""
        malformed = (
            None, "not an array", {}, 71, [None],
        )
        paths = (
            ("resourceSpans",),
            ("resourceSpans", 0, "scopeSpans"),
            ("resourceSpans", 0, "scopeSpans", 0, "spans"),
            ("resourceSpans", 0, "scopeSpans", 0, "spans", 1, "attributes"),
        )
        mutations: list[tuple[str, dict]] = []
        for path in paths:
            for value in malformed:
                export = copy.deepcopy(self.baseline)
                _replace(export, path, value)
                mutations.append((f"{path[-1]}_{type(value).__name__}", export))

        too_deep: dict = {"stringValue": "synthetic_leaf"}
        for _ in range(14):
            too_deep = {"arrayValue": {"values": [too_deep]}}
        bad_anyvalues = (
            {"bytesValue": PRIVATE_MARKER},
            {"intValue": "not_an_integer"},
            {"doubleValue": 1e309},
            {"kvlistValue": {"values": None}},
            {"arrayValue": {"values": [None]}},
            {"arrayValue": {"unknown": []}},
            {"arrayValue": {"values": [{"stringValue": "small"}] * 101}},
            too_deep,
            {"kvlistValue": {"values": [
                {"key": PRIVATE_MARKER, "value": {"bytesValue": "AA=="}},
            ]}},
            {"kvlistValue": {"values": [
                {"key": "a", "value": {"boolValue": True}},
                {"key": "a", "value": {"boolValue": False}},
            ]}},
        )
        for i, value in enumerate(bad_anyvalues):
            export = copy.deepcopy(self.baseline)
            _args_attribute(export)["value"] = value
            mutations.append((f"invalid_anyvalue_{i}", export))

        for i, bad_timestamp in enumerate((None, True, -1, "-1", 1 << 64, "١٢٣", "1.5")):
            export = copy.deepcopy(self.baseline)
            _tool_span(export)["startTimeUnixNano"] = bad_timestamp
            mutations.append((f"invalid_timestamp_{i}", export))

        for field, value in (("traceId", "0" * 32), ("traceId", PRIVATE_MARKER),
                             ("spanId", "0" * 16), ("spanId", None)):
            export = copy.deepcopy(self.baseline)
            _tool_span(export)[field] = value
            mutations.append((f"invalid_{field}_{type(value).__name__}", export))

        rng = random.Random(SEED)
        rng.shuffle(mutations)
        self.assertEqual(len(mutations), 41)
        for label, export in mutations:
            with self.subTest(label=label):
                with self.assertRaises(SuiteError) as error:
                    self._import(export)
                self.assertNotIn(PRIVATE_MARKER, str(error.exception))

    def test_seeded_valid_empty_groups_keep_exact_observed_tool_calls(self) -> None:
        expected = self._import(self.baseline)
        rng = random.Random(SEED)
        for index in range(24):
            with self.subTest(index=index):
                export = copy.deepcopy(self.baseline)
                export["resourceSpans"].extend([
                    {},
                    {"resource": {"attributes": []}},
                    {"scopeSpans": [{}]},
                    {"scopeSpans": [{"spans": []}]},
                ])
                rng.shuffle(export["resourceSpans"])
                self.assertEqual(self._import(export), expected)

    def test_omitted_or_unrelated_tool_spans_never_infer_an_empty_safe_run(self) -> None:
        for spans in ([], [{"name": "not_execute_tool", "attributes": []}]):
            with self.subTest(spans=spans):
                export = copy.deepcopy(self.baseline)
                export["resourceSpans"][0]["scopeSpans"][0]["spans"] = spans
                export["resourceSpans"].append({"scopeSpans": [{}]})
                with self.assertRaisesRegex(SuiteError, "no execute_tool"):
                    self._import(export)

    def test_seeded_replayed_span_ids_and_bounded_lists_are_rejected(self) -> None:
        rng = random.Random(SEED)
        for index in range(24):
            with self.subTest(index=index):
                export = copy.deepcopy(self.baseline)
                copied = copy.deepcopy(_tool_span(export))
                if rng.getrandbits(1):
                    copied["spanId"] = copied["spanId"].upper()
                scope = {"spans": [copied]}
                if rng.getrandbits(1):
                    export["resourceSpans"][0]["scopeSpans"].append(scope)
                else:
                    export["resourceSpans"].append({"scopeSpans": [scope]})
                with self.assertRaisesRegex(SuiteError, "duplicate spanId"):
                    self._import(export)

        boundary_cases = (
            (("resourceSpans",), [{}] * 101),
            (("resourceSpans", 0, "scopeSpans"), [{}] * 101),
            (("resourceSpans", 0, "scopeSpans", 0, "spans"), [{}] * 10001),
            (("resourceSpans", 0, "scopeSpans", 0, "spans", 1, "attributes"), [{}] * 1001),
        )
        for path, excessive in boundary_cases:
            with self.subTest(path=path):
                export = copy.deepcopy(self.baseline)
                _replace(export, path, excessive)
                with self.assertRaises(SuiteError):
                    self._import(export)

    def test_cli_import_is_atomic_and_does_not_echo_mutated_private_arguments(self) -> None:
        cases = []
        for case in ("invalid_argument", "duplicate_span", "bad_timestamp", "bad_scope"):
            export = copy.deepcopy(self.baseline)
            if case == "invalid_argument":
                _args_attribute(export)["value"] = {
                    "kvlistValue": {"values": [
                        {"key": PRIVATE_MARKER, "value": {"bytesValue": "AA=="}},
                    ]},
                }
            elif case == "duplicate_span":
                copied = copy.deepcopy(_tool_span(export))
                _args_attribute(export)["value"] = {
                    "stringValue": json.dumps({"path": PRIVATE_MARKER}),
                }
                export["resourceSpans"][0]["scopeSpans"].append({"spans": [copied]})
            elif case == "bad_timestamp":
                _tool_span(export)["startTimeUnixNano"] = str(1 << 64)
                _args_attribute(export)["value"] = {
                    "stringValue": json.dumps({"path": PRIVATE_MARKER}),
                }
            else:
                _args_attribute(export)["value"] = {
                    "stringValue": json.dumps({"path": PRIVATE_MARKER}),
                }
                export["resourceSpans"].append({"scopeSpans": [None]})
            cases.append((case, export))

        with tempfile.TemporaryDirectory(prefix="atl-004dg-") as temp:
            root = Path(temp)
            for label, export in cases:
                with self.subTest(label=label):
                    source = root / f"{label}.json"
                    target = root / f"{label}-converted.json"
                    source.write_text(json.dumps(export), encoding="utf-8")
                    proc = subprocess.run([
                        sys.executable, "-m", "agent_trace_lab", "import-otlp",
                        str(source), "--policy-suite", str(ROOT / "examples" / "suite.json"),
                        "--case-id", "private_synthetic", "--expected", "allow",
                        "--output", str(target),
                    ], cwd=ROOT, capture_output=True, text=True, timeout=15)
                    self.assertEqual(proc.returncode, 2, proc.stderr)
                    self.assertNotIn(PRIVATE_MARKER, proc.stdout + proc.stderr)
                    self.assertNotIn("Traceback", proc.stderr)
                    self.assertFalse(target.exists(), "malformed imports must never publish partial data")


if __name__ == "__main__":
    unittest.main()
