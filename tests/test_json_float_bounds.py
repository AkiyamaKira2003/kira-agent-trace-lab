"""Non-finite floating-point overflow must fail before imports or evaluation."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.schema import SuiteError, decode_json_arguments, load_json_document


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_MARKER = "PRIVATE_SYNTHETIC_FLOAT_SOURCE_73412"


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_trace_lab", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


class JsonFloatBoundsTests(unittest.TestCase):
    def test_outer_json_overflow_rejected_with_private_path_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / (PRIVATE_MARKER + ".json")
            source.write_text('{"n":1e9999}', encoding="utf-8")
            with self.assertRaises(SuiteError) as caught:
                load_json_document(source)
            self.assertIn("finite", str(caught.exception))
            self.assertNotIn(PRIVATE_MARKER, str(caught.exception))

    def test_embedded_tool_arguments_overflow_rejected(self):
        for token in ("1e9999", "-1e9999", "9.3e400"):
            with self.subTest(token=token):
                with self.assertRaises(SuiteError) as caught:
                    decode_json_arguments('{"count":' + token + '}', "tool.arguments")
                self.assertIn("finite", str(caught.exception))

    def test_legacy_10_suite_with_overflow_fails_closed_in_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / (PRIVATE_MARKER + ".json")
            output = Path(temp) / "not-created.json"
            suite = (
                '{"schema_version":"1.0",'
                '"policy":{"tools":{"search":{}},"max_actions":1},'
                '"cases":[{"id":"case","expected":"allow",'
                '"trace":[{"tool":"search","arguments":{"confidence":1e9999}}]}]}'
            )
            source.write_text(suite, encoding="utf-8")
            result = cli("evaluate", str(source), "--format", "json", "--output", str(output))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("finite", result.stderr)
            self.assertNotIn(PRIVATE_MARKER, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(output.exists())

    def test_responses_import_rejects_embedded_overflow_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / (PRIVATE_MARKER + ".json")
            output = Path(temp) / "not-created.json"
            source.write_text(json.dumps({
                "status": "completed",
                "output": [{"type": "function_call", "status": "completed",
                            "name": "search", "call_id": "call_1",
                            "arguments": '{"confidence":1e9999}'}],
            }), encoding="utf-8")
            result = cli(
                "import-responses", str(source),
                "--policy-suite", str(ROOT / "examples" / "suite.json"),
                "--case-id", "float_overflow", "--expected", "allow",
                "--output", str(output),
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("finite", result.stderr)
            self.assertNotIn(PRIVATE_MARKER, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(output.exists())

    def test_large_but_finite_floats_remain_usable(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "safe.json"
            source.write_text('{"max":1e308,"min":-1e308,"fraction":0.25}', encoding="utf-8")
            self.assertEqual(load_json_document(source), {
                "max": 1e308, "min": -1e308, "fraction": 0.25,
            })
        self.assertEqual(decode_json_arguments('{"rate":0.25}', "safe"), {"rate": 0.25})


if __name__ == "__main__":
    unittest.main()
