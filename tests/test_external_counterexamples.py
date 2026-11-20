"""Third-party synthetic action traces with documented attribution and label limitations."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from agent_trace_lab import evaluate_suite, load_suite

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "examples" / "agentdrift_counterexamples.json"


class ExternalCounterexampleTests(unittest.TestCase):
    def test_external_labels_expose_known_semantic_gap(self) -> None:
        report = evaluate_suite(load_suite(CORPUS))
        self.assertEqual([case["id"] for case in report["cases"]], [
            "agentdrift_banking_benign_0353",
            "agentdrift_email_attacked_full_0217",
        ])
        self.assertEqual(report["cases"][0]["actual"], "allow")
        self.assertTrue(report["cases"][0]["matched"])
        self.assertEqual(report["cases"][1]["actual"], "allow")
        self.assertFalse(report["cases"][1]["matched"])
        self.assertEqual(report["summary"]["confusion"], {"tp": 0, "tn": 1, "fp": 0, "fn": 1})
        self.assertEqual(report["summary"]["matched"], 1)
        self.assertIsNone(report["summary"]["deny_precision"])
        self.assertEqual(report["summary"]["deny_recall"], 0.0)

    def test_external_counterexample_cli_exits_nonzero(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "agent_trace_lab", "evaluate", str(CORPUS), "--format", "json"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["summary"]["confusion"]["fn"], 1)
        self.assertEqual(report["cases"][1]["violations"], [])


if __name__ == "__main__":
    unittest.main()
