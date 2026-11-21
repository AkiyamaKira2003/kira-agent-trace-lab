"""Bounded offline policy-delta witness isolation, with no raw trace output."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_trace_lab.engine import compare_policies
from agent_trace_lab.schema import load_json_document, load_suite


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples" / "demo_permissive.json"
CANDIDATE = ROOT / "examples" / "compare_candidate_task_guarded.json"
PRIVATE = "PRIVATE_SYNTHETIC_TOOL_ARGUMENT_79185"


def _triple() -> tuple[dict, dict]:
    source = load_suite(BASE)
    candidate = load_json_document(CANDIDATE)
    irrelevant = {"tool": "search_inbox", "arguments": {"query": PRIVATE}}
    source["cases"][0]["trace"] = [
        copy.deepcopy(irrelevant),
        copy.deepcopy(source["cases"][0]["trace"][0]),
        copy.deepcopy(irrelevant),
    ]
    return source, candidate


class MinimalWitnessTests(unittest.TestCase):
    def test_opt_in_finds_single_action_with_original_index_and_no_content(self):
        source, candidate = _triple()
        original = copy.deepcopy(source)
        default = compare_policies(source, candidate, redact_case_ids=True)
        self.assertNotIn("witness", default["cases"][0])
        report = compare_policies(
            source, candidate, redact_case_ids=True, minimal_witness=True,
        )
        row = report["cases"][0]
        self.assertEqual(row["id"], "case_0001")
        self.assertEqual((row["baseline"], row["candidate"]), ("allow", "deny"))
        self.assertEqual(row["witness"]["status"], "one_minimal")
        self.assertEqual(row["witness"]["event_indexes"], [1])
        self.assertGreater(row["witness"]["evaluations"], 0)
        self.assertNotIn(PRIVATE, json.dumps(report))
        self.assertNotIn("forward_email", json.dumps(report))
        self.assertEqual(source, original)
        self.assertEqual(
            report,
            compare_policies(source, candidate, redact_case_ids=True, minimal_witness=True),
        )

    def test_unchanged_case_has_no_witness_and_no_extra_evaluations(self):
        source, _ = _triple()
        candidate = {"schema_version": source["schema_version"], "policy": source["policy"]}
        report = compare_policies(source, candidate, minimal_witness=True)
        self.assertFalse(report["cases"][0]["changed"])
        self.assertIsNone(report["cases"][0]["witness"])

    def test_deny_to_allow_under_candidate_schema_downgrade(self):
        source = load_suite(ROOT / "examples" / "demo_task_scoped.json")
        candidate = load_json_document(BASE)
        report = compare_policies(
            source, {"schema_version": "1.0", "policy": candidate["policy"]},
            minimal_witness=True, redact_case_ids=True,
        )
        first = report["cases"][0]
        self.assertEqual((first["baseline"], first["candidate"]), ("deny", "allow"))
        self.assertEqual(first["witness"]["status"], "one_minimal")
        self.assertEqual(first["witness"]["event_indexes"], [0])
        self.assertNotIn("self-authored-fictional-demo-only", json.dumps(report))

    def test_opt_in_limits_per_case_trace_length(self):
        source, candidate = _triple()
        irrelevant = source["cases"][0]["trace"][0]
        significant = source["cases"][0]["trace"][1]
        source["cases"][0]["trace"] = [copy.deepcopy(irrelevant) for _ in range(69)] + [
            significant
        ]
        source["policy"]["max_actions"] = 100
        candidate["policy"]["max_actions"] = 100
        row = compare_policies(source, candidate, minimal_witness=True)["cases"][0]
        self.assertTrue(row["changed"])
        self.assertEqual(row["witness"]["status"], "skipped_trace_limit")
        self.assertIsNone(row["witness"]["event_indexes"])
        self.assertEqual(row["witness"]["evaluations"], 0)

    def test_opt_in_limits_changed_cases(self):
        source, candidate = _triple()
        prototype = copy.deepcopy(source["cases"][0])
        for i in range(6):
            case = copy.deepcopy(prototype)
            case["id"] = f"more_{i}"
            source["cases"].append(case)
        report = compare_policies(source, candidate, minimal_witness=True)
        self.assertEqual(report["summary"]["changed"], 7)
        self.assertEqual(
            [r["witness"]["status"] for r in report["cases"]],
            ["one_minimal"] * 5 + ["skipped_case_limit"] * 2,
        )

    def test_budget_exhaustion_never_claims_one_minimal(self):
        source, candidate = _triple()
        with patch("agent_trace_lab.engine._MAX_WITNESS_EVALUATIONS", 1):
            row = compare_policies(source, candidate, minimal_witness=True)["cases"][0]
        witness = row["witness"]
        self.assertEqual(witness["status"], "budget_exhausted")
        self.assertEqual(witness["evaluations"], 1)
        self.assertNotEqual(witness["event_indexes"], [1])
        # Even an incomplete result must still reproduce the *same* delta.
        source["cases"][0]["trace"] = [
            source["cases"][0]["trace"][index] for index in witness["event_indexes"]
        ]
        reproduced = compare_policies(source, candidate)["cases"][0]
        self.assertEqual((reproduced["baseline"], reproduced["candidate"]), ("allow", "deny"))

    def test_witness_flag_requires_exact_boolean(self):
        source, candidate = _triple()
        with self.assertRaisesRegex(ValueError, "boolean"):
            compare_policies(source, candidate, minimal_witness=1)

    def test_one_minimal_invariant_on_seeded_trace_variations(self):
        rng = random.Random(20261121)
        baseline, candidate = _triple()
        baseline["policy"]["max_actions"] = 30
        candidate["policy"]["max_actions"] = 30
        search = baseline["cases"][0]["trace"][0]
        forward = baseline["cases"][0]["trace"][1]
        for iteration in range(80):
            with self.subTest(iteration=iteration):
                length = rng.randrange(1, 17)
                events = [copy.deepcopy(rng.choice((search, search, forward))) for _ in range(length)]
                baseline["cases"][0]["trace"] = events
                result = compare_policies(baseline, candidate, minimal_witness=True)["cases"][0]
                if not result["changed"]:
                    self.assertIsNone(result["witness"])
                    continue
                witness = result["witness"]
                self.assertEqual(witness["status"], "one_minimal")
                selected = witness["event_indexes"]
                self.assertEqual(selected, sorted(selected))
                self.assertEqual(len(selected), len(set(selected)))
                for position in range(len(selected)):
                    shortened = [events[index] for i, index in enumerate(selected) if i != position]
                    baseline["cases"][0]["trace"] = shortened
                    after_drop = compare_policies(baseline, candidate)["cases"][0]
                    self.assertNotEqual(
                        (after_drop["baseline"], after_drop["candidate"]),
                        (result["baseline"], result["candidate"]),
                    )
                baseline["cases"][0]["trace"] = events

    def test_cli_json_and_text_redacted_and_summary_incompatibility(self):
        source, _ = _triple()
        source["cases"][0]["id"] = "PRIVATE_CASE_IDENTIFIER_79185"
        with tempfile.TemporaryDirectory() as folder:
            location = Path(folder) / "input.json"
            location.write_text(json.dumps(source), encoding="utf-8")
            command = [
                sys.executable, "-m", "agent_trace_lab", "compare-policies",
                str(location), "--candidate-policy", str(CANDIDATE),
                "--redact-case-ids", "--witness",
            ]
            for format_args in (["--format", "json"], ["--format", "text"]):
                with self.subTest(fmt=format_args):
                    proc = subprocess.run(
                        command + format_args, cwd=ROOT,
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn("case_0001", proc.stdout)
                    self.assertIn("one_minimal", proc.stdout)
                    self.assertNotIn(PRIVATE, proc.stdout + proc.stderr)
                    self.assertNotIn("forward_email", proc.stdout + proc.stderr)
                    self.assertNotIn("Traceback", proc.stderr)
            summary = subprocess.run(
                command + ["--summary-only"], cwd=ROOT,
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(summary.returncode, 2)
            self.assertIn("summary-only", summary.stderr)
            self.assertNotIn(PRIVATE, summary.stdout + summary.stderr)


if __name__ == "__main__":
    unittest.main()
