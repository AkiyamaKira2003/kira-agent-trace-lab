"""Synthetic tests for read-only OpenAI Responses function_call output import."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.engine import evaluate_suite
from agent_trace_lab.responses import import_responses_output
from agent_trace_lab.schema import SuiteError, load_json_document, load_suite

ROOT = Path(__file__).resolve().parents[1]
RESPONSE = ROOT / "examples" / "responses_function_calls_synthetic.json"
POLICY = ROOT / "examples" / "suite.json"
PRIVATE_MARKER = "PRIVATE_SELF_AUTHORED_MARKER_9498123"


class ResponsesImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.response = load_json_document(RESPONSE)
        self.policy = load_suite(POLICY)["policy"]

    def convert(self, response=None, *, policy=None, expected="allow"):
        return import_responses_output(
            self.response if response is None else response,
            policy=self.policy if policy is None else policy,
            case_id="synthetic_case", expected=expected,
        )

    def test_reads_only_function_calls_and_preserves_order(self):
        suite = self.convert()
        self.assertEqual(suite["schema_version"], "1.0")
        self.assertEqual(suite["cases"][0]["trace"], [
            {"tool": "docs.search", "arguments": {"query": "README"}},
            {"tool": "files.read", "arguments": {"path": "/workspace/docs/guide.md"}},
        ])
        self.assertEqual(evaluate_suite(suite)["summary"]["matched"], 1)
        self.assertEqual(self.convert(), suite)
        self.assertNotIn("output", suite)
        self.assertNotIn("call_id", json.dumps(suite))

    def test_caller_label_is_not_inferred_from_response(self):
        self.response["model"] = "self-authored-test-model"
        self.response["usage"] = {"output_tokens": 123}
        self.assertEqual(evaluate_suite(self.convert(expected="deny"))["summary"]["matched"], 0)

    def test_absent_grant_remains_absent_with_task_guarded_policy(self):
        policy = load_suite(ROOT / "examples" / "task_grants.json")["policy"]
        response = copy.deepcopy(self.response)
        response["output"][1]["name"] = "forward_email"
        response["output"][1]["arguments"] = '{"to":"alice@example.org","ids":["msg_1234"]}'
        response["output"] = [response["output"][1]]
        suite = self.convert(response, policy=policy, expected="deny")
        self.assertEqual(suite["schema_version"], "1.1")
        self.assertNotIn("task_authorization", suite["cases"][0])
        self.assertIn("TASK_GRANT_REQUIRED",
                      [v["code"] for v in evaluate_suite(suite)["cases"][0]["violations"]])

    def test_incomplete_response_or_function_call_rejected(self):
        response = copy.deepcopy(self.response)
        del response["status"]
        with self.assertRaisesRegex(SuiteError, "not completed"):
            self.convert(response)
        for status in ("in_progress", "incomplete", "failed", None):
            with self.subTest(status=status):
                response = copy.deepcopy(self.response)
                response["status"] = status
                with self.assertRaisesRegex(SuiteError, "not completed"):
                    self.convert(response)
        for status in ("in_progress", "incomplete"):
            response = copy.deepcopy(self.response)
            response["output"][1]["status"] = status
            with self.assertRaisesRegex(SuiteError, "not completed"):
                self.convert(response)

    def test_missing_or_oversized_output_fails_closed(self):
        for value in (None, [], "not an array", [{}] * 1001):
            with self.subTest(size=str(type(value))):
                response = copy.deepcopy(self.response)
                response["output"] = value
                with self.assertRaises(SuiteError):
                    self.convert(response)

    def test_no_function_call_must_not_be_silent_allow(self):
        self.response["output"] = [{"type": "message", "content": []}]
        with self.assertRaisesRegex(SuiteError, "no completed function calls"):
            self.convert()

    def test_unsupported_hosted_or_unknown_call_refused(self):
        for kind in ("computer_call", "web_search_call", "mcp_call", "custom_tool_call",
                     "file_search_call", "function_call_output", "unrecognized"):
            with self.subTest(kind=kind):
                response = copy.deepcopy(self.response)
                response["output"].append({"type": kind})
                with self.assertRaisesRegex(SuiteError, "unsupported output item"):
                    self.convert(response)

    def test_malformed_or_duplicate_call_identifiers(self):
        for replacement in ("", None, "x" * 129, "call_synthetic_02"):
            with self.subTest(value=str(replacement)[:20]):
                response = copy.deepcopy(self.response)
                response["output"][1]["call_id"] = replacement
                with self.assertRaisesRegex(SuiteError, "call_id"):
                    self.convert(response)

    def test_missing_or_invalid_name_fails_closed(self):
        for value in (None, "", PRIVATE_MARKER + "X" * 100):
            response = copy.deepcopy(self.response)
            response["output"][1]["name"] = value
            with self.assertRaises(SuiteError) as error:
                self.convert(response)
            self.assertNotIn(PRIVATE_MARKER, str(error.exception))

    def test_missing_or_non_string_arguments_rejected(self):
        for args in (None, {}, [], 123):
            response = copy.deepcopy(self.response)
            response["output"][1]["arguments"] = args
            with self.assertRaisesRegex(SuiteError, "JSON-object string"):
                self.convert(response)
        del self.response["output"][1]["arguments"]
        with self.assertRaisesRegex(SuiteError, "missing"):
            self.convert()

    def test_bad_json_and_duplicate_argument_names_rejected_without_leak(self):
        for args in (
            '{"query":',
            '["array is not an object"]',
            '{"query": NaN}',
            '{"' + PRIVATE_MARKER + '":1,"' + PRIVATE_MARKER + '":2}',
        ):
            response = copy.deepcopy(self.response)
            response["output"][1]["arguments"] = args
            with self.assertRaises(SuiteError) as error:
                self.convert(response)
            self.assertNotIn(PRIVATE_MARKER, str(error.exception))

    def test_nested_argument_size_guard(self):
        response = copy.deepcopy(self.response)
        response["output"][1]["arguments"] = json.dumps({"query": list(range(1001))})
        with self.assertRaisesRegex(SuiteError, "oversized list"):
            self.convert(response)

    def test_input_object_and_item_shape_checked(self):
        with self.assertRaisesRegex(SuiteError, "one response"):
            self.convert([])
        response = copy.deepcopy(self.response)
        response["output"][0] = PRIVATE_MARKER
        with self.assertRaises(SuiteError) as error:
            self.convert(response)
        self.assertNotIn(PRIVATE_MARKER, str(error.exception))

    def test_cli_roundtrip_no_clobber_explicit_overwrite_and_input_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "imported.json"
            args = [
                sys.executable, "-m", "agent_trace_lab", "import-responses", str(RESPONSE),
                "--policy-suite", str(POLICY), "--case-id", "synthetic_case",
                "--expected", "allow", "--output", str(output),
            ]
            def invoke(extra=()):
                return subprocess.run(
                    [*args, *extra], cwd=ROOT, text=True,
                    capture_output=True, timeout=15,
                )
            first = invoke()
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("No calls executed", first.stdout)
            self.assertEqual(evaluate_suite(load_suite(output))["summary"]["matched"], 1)
            before = output.read_bytes()
            blocked = invoke()
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(before, output.read_bytes())
            explicit = invoke(("--overwrite",))
            self.assertEqual(explicit.returncode, 0, explicit.stderr)
            self.assertEqual(load_suite(output)["cases"][0]["id"], "synthetic_case")
            self.assertEqual(invoke(("--output", str(RESPONSE), "--overwrite")).returncode, 2)
            self.assertEqual(invoke(("--output", str(POLICY), "--overwrite")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
