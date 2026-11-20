"""ATL-004P: malformed JSON diagnostics must not echo untrusted keys."""

from __future__ import annotations

from contextlib import redirect_stderr
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_trace_lab.cli import main
from agent_trace_lab.schema import SuiteError, load_json_document, validate_suite
from scripts.verify_installed_wheel import verify_installed_diagnostic

MARKER = "SECRET_FIELD_DO_NOT_PRINT_98765"


def minimal_suite() -> dict:
    return {
        "schema_version": "1.0",
        "policy": {"max_actions": 2, "tools": {"search_inbox": {}}},
        "cases": [{"id": "case_a", "expected": "allow", "trace": []}],
    }


class DiagnosticRedactionTests(unittest.TestCase):
    def test_unknown_case_field_name_is_not_echoed(self):
        data = minimal_suite()
        data["cases"][0][MARKER] = "private value"
        with self.assertRaises(SuiteError) as ctx:
            validate_suite(data)
        self.assertIn("unexpected_count=1", str(ctx.exception))
        self.assertNotIn(MARKER, str(ctx.exception))
        self.assertNotIn("private value", str(ctx.exception))

    def test_unknown_tool_config_field_and_tool_identifier_are_redacted(self):
        data = minimal_suite()
        data["policy"]["tools"] = {f"tool_{MARKER}": {MARKER: "private value"}}
        with self.assertRaises(SuiteError) as ctx:
            validate_suite(data)
        error = str(ctx.exception)
        self.assertIn("policy.tools[0]", error)
        self.assertIn("unexpected_count=1", error)
        self.assertNotIn(MARKER, error)
        self.assertNotIn("private value", error)

    def test_invalid_tool_identifier_is_not_echoed(self):
        data = minimal_suite()
        data["policy"]["tools"] = {f"{MARKER}@example.invalid": {}}
        with self.assertRaises(SuiteError) as ctx:
            validate_suite(data)
        self.assertIn("invalid tool name", str(ctx.exception))
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_other_tool_validation_errors_use_safe_index_not_name(self):
        data = minimal_suite()
        data["policy"]["tools"] = {f"tool_{MARKER}": {"url_args": ["url"]}}
        with self.assertRaises(SuiteError) as ctx:
            validate_suite(data)
        self.assertIn("policy.tools[0]", str(ctx.exception))
        self.assertIn("must be paired", str(ctx.exception))
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_duplicate_json_property_name_not_echoed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(
                '{"' + MARKER + '":"first","' + MARKER + '":"second"}',
                encoding="utf-8",
            )
            with self.assertRaises(SuiteError) as ctx:
                load_json_document(path)
        self.assertIn("duplicate JSON property", str(ctx.exception))
        self.assertNotIn(MARKER, str(ctx.exception))

    def test_cli_stderr_does_not_echo_unknown_json_key(self):
        data = minimal_suite()
        data["cases"][0][MARKER] = "private value"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformed.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = main(["evaluate", str(path), "--format", "json"])
        self.assertEqual(exit_code, 2)
        self.assertIn("unexpected_count=1", stderr.getvalue())
        self.assertNotIn(MARKER, stderr.getvalue())
        self.assertNotIn("private value", stderr.getvalue())

    def test_redaction_does_not_loosen_any_schema_validation(self):
        data = minimal_suite()
        self.assertEqual(validate_suite(deepcopy(data)), data)
        data["cases"][0].pop("id")
        with self.assertRaises(SuiteError) as ctx:
            validate_suite(data)
        self.assertIn("missing=", str(ctx.exception))
        self.assertIn("id", str(ctx.exception))  # static schema field only

    def test_installed_diagnostic_probe_accepts_only_safe_exit_two(self):
        valid = subprocess.CompletedProcess(
            ["python"], 2, stdout="",
            stderr="error: cases[0]: missing=[], unexpected_count=1",
        )
        with patch("scripts.verify_installed_wheel.subprocess.run", return_value=valid):
            verify_installed_diagnostic(["python"], Path("."), {}, MARKER)
        for code, stdout, stderr in (
            (0, "", "error: unexpected_count=1"),
            (2, "", f"error: {MARKER} unexpected_count=1"),
            (2, MARKER, "error: unexpected_count=1"),
            (2, "", "error: malformed input with no redaction count"),
        ):
            with self.subTest(code=code, stdout=stdout, stderr=stderr):
                bad = subprocess.CompletedProcess(
                    ["python"], code, stdout=stdout, stderr=stderr,
                )
                with patch("scripts.verify_installed_wheel.subprocess.run", return_value=bad):
                    with self.assertRaises(SuiteError) as ctx:
                        verify_installed_diagnostic(["python"], Path("."), {}, MARKER)
                self.assertNotIn(MARKER, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
