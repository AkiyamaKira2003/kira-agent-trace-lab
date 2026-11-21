"""JSON integer limits must be stable and private-input-safe across importers."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.schema import SuiteError, decode_json_arguments, load_json_document


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_MARKER = "PRIVATE_SYNTHETIC_JSON_SOURCE_6214"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_trace_lab", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


class JsonIntegerBoundsTests(unittest.TestCase):
    def test_large_integer_in_outer_json_is_safe_input_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / (PRIVATE_MARKER + ".json")
            path.write_bytes(b'{"private_key":' + b"9" * 5000 + b"}")
            with self.assertRaises(SuiteError) as caught:
                load_json_document(path)
            self.assertIn("JSON integer", str(caught.exception))
            self.assertNotIn(PRIVATE_MARKER, str(caught.exception))

            result = _cli("evaluate", str(path))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("JSON integer", result.stderr)
            self.assertNotIn(PRIVATE_MARKER, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_large_integer_in_encoded_arguments_fails_without_traceback(self):
        huge_arguments = '{"query":' + "9" * 5000 + "}"
        with self.assertRaises(SuiteError) as caught:
            decode_json_arguments(huge_arguments, "synthetic.arguments")
        self.assertIn("JSON integer", str(caught.exception))

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / (PRIVATE_MARKER + ".json")
            destination = Path(folder) / "not-created.json"
            export = load_json_document(ROOT / "examples" / "otlp_spans.json")
            tool_span = export["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
            tool_span["attributes"][2]["value"] = {"stringValue": huge_arguments}
            source.write_text(json.dumps(export), encoding="utf-8")
            result = _cli(
                "import-otlp", str(source),
                "--policy-suite", str(ROOT / "examples" / "suite.json"),
                "--case-id", "integer_limit",
                "--expected", "allow", "--output", str(destination),
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("JSON integer", result.stderr)
            self.assertNotIn(PRIVATE_MARKER, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(destination.exists())

    def test_decimal_boundary_remains_cross_python_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "numeric.json"
            source.write_bytes(b'{"n":' + b"7" * 4300 + b"}")
            self.assertIsInstance(load_json_document(source)["n"], int)
            source.write_bytes(b'{"n":' + b"7" * 4301 + b"}")
            with self.assertRaises(SuiteError):
                load_json_document(source)
        self.assertEqual(decode_json_arguments('{"count":42}', "safe"), {"count": 42})
        with self.assertRaisesRegex(SuiteError, "duplicate JSON property"):
            decode_json_arguments('{"count":1,"count":2}', "safe")


if __name__ == "__main__":
    unittest.main()
