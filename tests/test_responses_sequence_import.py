"""ATL-004AF bounded local multi-Responses object archive, never action replay."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.engine import evaluate_suite
from agent_trace_lab.responses import import_responses_sequence, import_responses_output
from agent_trace_lab.schema import SuiteError, load_json_document, load_suite

ROOT = Path(__file__).resolve().parents[1]
SEQUENCE = ROOT / "examples" / "responses_sequence_synthetic.json"
POLICY = ROOT / "examples" / "suite.json"
SECRET = "PRIVATE_SYNTHETIC_TOOL_MARKER_481520"


class ResponsesSequenceTests(unittest.TestCase):
    def setUp(self):
        self.responses = load_json_document(SEQUENCE)
        self.policy = load_suite(POLICY)["policy"]

    def convert(self, values=None, *, expected="allow", policy=None):
        return import_responses_sequence(
            self.responses if values is None else values,
            policy=self.policy if policy is None else policy,
            case_id="sequence_demo", expected=expected,
        )

    def test_preserves_order_across_message_only_response(self):
        suite = self.convert()
        self.assertEqual(suite["cases"][0]["trace"], [
            {"tool": "docs.search", "arguments": {"query": "README"}},
            {"tool": "files.read", "arguments": {"path": "/workspace/docs/guide.md"}},
        ])
        self.assertEqual(evaluate_suite(suite)["summary"]["matched"], 1)
        self.assertEqual(self.convert(), suite)
        self.assertNotIn("call_id", json.dumps(suite))
        self.assertNotIn("previous_response_id", json.dumps(suite))

    def test_does_not_mutate_archived_inputs_or_infer_authorization(self):
        original = copy.deepcopy(self.responses)
        suite = self.convert(expected="deny")
        self.assertEqual(self.responses, original)
        self.assertEqual(evaluate_suite(suite)["summary"]["matched"], 0)
        self.assertNotIn("task_authorization", suite["cases"][0])
        task_policy = load_suite(ROOT / "examples" / "task_grants.json")["policy"]
        guarded = copy.deepcopy(self.responses)
        guarded[2]["output"][1]["name"] = "forward_email"
        guarded[2]["output"][1]["arguments"] = '{"to":"alice@example.org","ids":["msg_1234"]}'
        result = self.convert(guarded, policy=task_policy, expected="deny")
        self.assertIn("TASK_GRANT_REQUIRED",
                      [violation["code"] for violation in evaluate_suite(result)["cases"][0]["violations"]])

    def test_api_single_response_import_contract_remains_separate(self):
        with self.assertRaisesRegex(SuiteError, "one response"):
            import_responses_output(self.responses, policy=self.policy,
                                    case_id="one", expected="allow")

    def test_requires_bounded_nonempty_local_array(self):
        for value in (None, {}, [], [self.responses[0]] * 51):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaisesRegex(SuiteError, "1..50"):
                    import_responses_sequence(
                        value, policy=self.policy,
                        case_id="sequence_demo", expected="allow",
                    )
        with self.assertRaisesRegex(SuiteError, "JSON object"):
            self.convert([123])

    def test_response_ids_unique_nonempty_bounded_without_unsafe_diagnostics(self):
        for replacement in ("", None, SECRET * 10, self.responses[0]["id"]):
            sequence = copy.deepcopy(self.responses)
            sequence[1]["id"] = replacement
            with self.assertRaises(SuiteError) as caught:
                self.convert(sequence)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_declared_chain_must_match_immediate_previous_id(self):
        for index, value in ((0, "resp_not_previous"), (1, "resp_wrong"),
                             (2, self.responses[0]["id"])):
            sequence = copy.deepcopy(self.responses)
            sequence[index]["previous_response_id"] = value
            with self.subTest(index=index):
                with self.assertRaisesRegex(SuiteError, "previous_response_id"):
                    self.convert(sequence)
        # Omitted/null links do not establish causality. The archive explicitly
        # asserts item order, even if API context was manually managed.
        sequence = copy.deepcopy(self.responses)
        sequence[1].pop("previous_response_id")
        sequence[2]["previous_response_id"] = None
        self.assertEqual(self.convert(sequence), self.convert())

    def test_duplicate_function_call_id_rejected_across_responses(self):
        sequence = copy.deepcopy(self.responses)
        sequence[2]["output"][1]["call_id"] = sequence[0]["output"][0]["call_id"]
        with self.assertRaisesRegex(SuiteError, "unique string"):
            self.convert(sequence)

    def test_incomplete_or_unsupported_items_fail_closed(self):
        for index in (0, 1, 2):
            sequence = copy.deepcopy(self.responses)
            sequence[index]["status"] = "in_progress"
            with self.assertRaisesRegex(SuiteError, "not completed"):
                self.convert(sequence)
        for unsupported in ("computer_call", "mcp_call", "web_search_call",
                            "function_call_output", "custom_tool_call", SECRET):
            sequence = copy.deepcopy(self.responses)
            sequence[1]["output"].append({"type": unsupported})
            with self.assertRaises(SuiteError) as caught:
                self.convert(sequence)
            self.assertNotIn(SECRET, str(caught.exception))
        sequence = copy.deepcopy(self.responses)
        sequence[2]["output"][1]["status"] = "incomplete"
        with self.assertRaises(SuiteError):
            self.convert(sequence)

    def test_bounded_per_response_and_total_items(self):
        sequence = copy.deepcopy(self.responses)
        sequence[0]["output"] = [{"type": "message", "content": []}] * 1001
        with self.assertRaisesRegex(SuiteError, "1..1000"):
            self.convert(sequence)
        # 50 x 201 valid output items, but > MAX_EVENTS=10000 cumulative.
        responses = [{
            "id": f"resp_{i}",
            "status": "completed",
            "output": [{"type": "message", "content": []}] * 201,
        } for i in range(50)]
        with self.assertRaisesRegex(SuiteError, "bounded output item count"):
            self.convert(responses)
        empty_calls = [{
            "id": "resp_empty", "status": "completed",
            "output": [{"type": "message", "content": []}],
        }]
        with self.assertRaisesRegex(SuiteError, "no completed function calls"):
            self.convert(empty_calls)

    def test_invalid_arguments_and_private_keys_rejected_without_echo(self):
        for value in ('{"query":', '{"' + SECRET + '":1,"' + SECRET + '":2}',
                      '{"query": NaN}', '["array"]', None):
            sequence = copy.deepcopy(self.responses)
            sequence[2]["output"][1]["arguments"] = value
            with self.assertRaises(SuiteError) as caught:
                self.convert(sequence)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_cli_roundtrip_atomic_no_clobber_and_input_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "imported.json"
            args = [
                sys.executable, "-m", "agent_trace_lab", "import-responses-sequence",
                str(SEQUENCE), "--policy-suite", str(POLICY),
                "--case-id", "sequence_demo", "--expected", "allow",
                "--output", str(out),
            ]
            def invoke(extra=()):
                return subprocess.run(
                    [*args, *extra], cwd=ROOT, capture_output=True, text=True, timeout=15,
                )
            first = invoke()
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("No calls executed", first.stdout)
            self.assertEqual(len(load_suite(out)["cases"][0]["trace"]), 2)
            before = out.read_bytes()
            self.assertEqual(invoke().returncode, 2)
            self.assertEqual(out.read_bytes(), before)
            self.assertEqual(invoke(("--overwrite",)).returncode, 0)
            self.assertEqual(out.read_bytes(), before)
            input_bytes = SEQUENCE.read_bytes()
            self.assertEqual(invoke(("--output", str(SEQUENCE), "--overwrite")).returncode, 2)
            self.assertEqual(SEQUENCE.read_bytes(), input_bytes)
            self.assertEqual(invoke(("--output", str(POLICY), "--overwrite")).returncode, 2)
            self.assertEqual(list(Path(tmp).glob(".agent-trace-import-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
