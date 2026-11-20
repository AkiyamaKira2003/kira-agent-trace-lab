"""ATL-004AH: real CLI filesystem/JSON errors must not echo private paths."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agent_trace_lab.schema import load_json_document, SuiteError

ROOT = Path(__file__).resolve().parents[1]
MARKER = "PRIVATE_SYNTHETIC_PATH_948127"
IMPORTS = (
    ("import-otlp", "otlp_spans.json", "suite.json"),
    ("import-swe", "swe_recorded_row_synthetic.json", "swe_structural_policy.json"),
    ("import-agentdojo", "agentdojo_recorded_synthetic.json", "agentdojo_policy_simulated_scope.json"),
    ("import-responses", "responses_function_calls_synthetic.json", "suite.json"),
    ("import-responses-sequence", "responses_sequence_synthetic.json", "suite.json"),
)


def invoke(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_trace_lab", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=15,
    )


def importer_args(command: str, input_file: Path, policy_file: Path, output: Path) -> list[str]:
    return [
        command, str(input_file), "--policy-suite", str(policy_file),
        "--case-id", "synthetic_case", "--expected", "allow",
        "--output", str(output),
    ]


class CliIODiagnosticPrivacyTests(unittest.TestCase):
    def test_all_five_importers_hide_private_output_parent_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private_parent = root / MARKER
            original = b"DO_NOT_REPLACE_SYNTHETIC_PARENT"
            private_parent.write_bytes(original)  # regular file, not directory
            output = private_parent / "report.json"
            for command, input_name, policy_name in IMPORTS:
                with self.subTest(command=command):
                    result = invoke(importer_args(
                        command, ROOT / "examples" / input_name,
                        ROOT / "examples" / policy_name, output,
                    ))
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("filesystem I/O operation failed", result.stderr)
                    self.assertNotIn(MARKER, result.stdout + result.stderr)
                    self.assertEqual(private_parent.read_bytes(), original)
                    self.assertFalse(output.exists())
            self.assertFalse(tuple(root.glob(".agent-trace-import-*.tmp")))

    def test_missing_private_input_is_redacted_for_every_command(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            missing = root / (MARKER + ".json")
            commands = [
                ["evaluate", str(missing)],
                ["compare-policies", str(missing), "--candidate-policy",
                 str(ROOT / "examples" / "compare_candidate_task_guarded.json")],
            ]
            for command, _, policy_name in IMPORTS:
                commands.append(importer_args(
                    command, missing, ROOT / "examples" / policy_name,
                    root / f"{command}.json",
                ))
            for args in commands:
                with self.subTest(command=args[0]):
                    result = invoke(args)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("cannot read valid UTF-8 JSON suite", result.stderr)
                    self.assertIn("filesystem I/O failure", result.stderr)
                    self.assertNotIn(MARKER, result.stdout + result.stderr)
            self.assertEqual(list(root.glob("*.json")), [])

    def test_loader_keeps_informative_bounded_error_categories(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, content, category in (
                ("malformed", b'{"' + MARKER.encode() + b'":', "malformed JSON"),
                ("invalid_utf8", b'{"a":"\xff"}', "invalid UTF-8"),
                ("oversized", b" " * (2 * 1024 * 1024 + 1), "input file exceeds"),
                ("duplicate_property", b'{"a":1,"a":2}', "duplicate JSON property"),
            ):
                with self.subTest(name=name):
                    source = root / (MARKER + name + ".json")
                    source.write_bytes(content)
                    with self.assertRaises(SuiteError) as caught:
                        load_json_document(source)
                    self.assertIn(category, str(caught.exception))
                    self.assertNotIn(MARKER, str(caught.exception))
                    result = invoke(["evaluate", str(source)])
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(category, result.stderr)
                    self.assertNotIn(MARKER, result.stdout + result.stderr)

    def test_valid_cli_imports_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for command, input_name, policy_name in IMPORTS:
                with self.subTest(command=command):
                    output = root / f"{command}.json"
                    result = invoke(importer_args(
                        command, ROOT / "examples" / input_name,
                        ROOT / "examples" / policy_name, output,
                    ))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(output.is_file())
                    first = output.read_bytes()
                    blocked = invoke(importer_args(
                        command, ROOT / "examples" / input_name,
                        ROOT / "examples" / policy_name, output,
                    ))
                    self.assertEqual(blocked.returncode, 2)
                    self.assertIn("already exists", blocked.stderr)
                    self.assertEqual(output.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
