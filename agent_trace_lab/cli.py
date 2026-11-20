"""Command-line interface. Exit 0 = all expected verdicts matched; 1 = mismatch; 2 = input failure."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .engine import evaluate_suite
from .schema import SuiteError, load_json_document, load_suite
from .otlp import import_otlp
from .swe import import_swe_row
from .agentdojo import import_agentdojo_run


def _write_import_suite(path: Path, suite: dict, *, overwrite: bool) -> None:
    """Commit complete imported JSON without exposing a partial destination."""
    payload = json.dumps(suite, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and path.is_symlink():
        raise SuiteError("refusing --overwrite on a symbolic-link output")
    # Write the full payload to a private same-directory temporary file.
    # Link without replacement by default; use atomic replace only when
    # explicitly requested. No partial data is exposed at the final path.
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".agent-trace-import-", suffix=".tmp", delete=False,
        ) as stream:
            tmp_path = Path(stream.name)
            stream.write(payload)
        if overwrite:
            os.replace(tmp_path, path)
        else:
            try:
                os.link(tmp_path, path)
            except FileExistsError as exc:
                raise SuiteError(
                    "output already exists; choose a new path or use --overwrite"
                ) from exc
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-trace-lab", description="Offline policy audit of AI-agent tool traces")
    subcommands = parser.add_subparsers(dest="command", required=True)
    evaluate = subcommands.add_parser("evaluate", help="evaluate a JSON suite without executing its tool actions")
    evaluate.add_argument("suite", type=Path)
    evaluate.add_argument("--format", choices=("text", "json"), default="text")
    evaluate.add_argument("--output", type=Path, help="write report to file instead of stdout")
    importer = subcommands.add_parser("import-otlp", help="convert recorded OTLP JSON tool spans into a suite")
    importer.add_argument("otlp", type=Path, help="saved OTLP/HTTP JSON export")
    importer.add_argument("--policy-suite", type=Path, required=True, help="validated suite providing the policy")
    importer.add_argument("--case-id", required=True, help="unique ID for the imported case")
    importer.add_argument("--expected", choices=("allow", "deny"), required=True, help="human-provided ground truth label")
    importer.add_argument("--output", type=Path, required=True, help="output suite file (may contain sensitive arguments)")
    importer.add_argument("--overwrite", action="store_true", help="explicitly replace an existing regular output file")
    swe = subcommands.add_parser("import-swe", help="convert a local recorded SWE tool-call row into a suite")
    swe.add_argument("row", type=Path, help="a single saved JSON row, not a dataset API response envelope")
    swe.add_argument("--policy-suite", type=Path, required=True, help="validated suite providing the policy")
    swe.add_argument("--case-id", required=True, help="unique ID for the imported case")
    swe.add_argument("--expected", choices=("allow", "deny"), required=True, help="caller-supplied label, never inferred from resolved")
    swe.add_argument("--output", type=Path, required=True, help="output suite file (may contain sensitive arguments)")
    swe.add_argument("--overwrite", action="store_true", help="explicitly replace an existing regular output file")
    dojo = subcommands.add_parser("import-agentdojo", help="convert a locally saved AgentDojo recorded run into a suite")
    dojo.add_argument("run", type=Path, help="one AgentDojo JSON run; no remote fetch or replay")
    dojo.add_argument("--policy-suite", type=Path, required=True, help="validated suite providing the policy")
    dojo.add_argument("--case-id", required=True, help="unique ID for the imported case")
    dojo.add_argument("--expected", choices=("allow", "deny"), required=True, help="caller-reviewed scenario label; never inferred from the run")
    dojo.add_argument("--output", type=Path, required=True, help="private output suite (may include recorded argument values)")
    dojo.add_argument("--overwrite", action="store_true", help="explicitly replace an existing regular output file")
    args = parser.parse_args(argv)
    try:
        if args.command == "import-agentdojo":
            if args.output.resolve() in (args.run.resolve(), args.policy_suite.resolve()):
                raise SuiteError("refusing to overwrite the AgentDojo run or policy suite")
            policy = load_suite(args.policy_suite)["policy"]
            suite = import_agentdojo_run(
                load_json_document(args.run),
                policy=policy,
                case_id=args.case_id,
                expected=args.expected,
            )
            _write_import_suite(args.output, suite, overwrite=args.overwrite)
            print(
                f"Imported {len(suite['cases'][0]['trace'])} recorded AgentDojo tool calls. "
                "Expected label is caller-provided, not inferred from the benchmark's utility/security flags. "
                "No calls were executed. Output may contain sensitive arguments; redact before sharing."
            )
            return 0
        if args.command == "import-swe":
            if args.output.resolve() in (args.row.resolve(), args.policy_suite.resolve()):
                raise SuiteError("refusing to overwrite the source SWE row or policy suite")
            policy = load_suite(args.policy_suite)["policy"]
            suite = import_swe_row(
                load_json_document(args.row),
                policy=policy,
                case_id=args.case_id,
                expected=args.expected,
            )
            _write_import_suite(args.output, suite, overwrite=args.overwrite)
            print(
                f"Imported {len(suite['cases'][0]['trace'])} recorded tool calls. "
                "Label was caller-provided and is not independently verified. "
                "The output contains arguments that may be sensitive; review/redact before sharing."
            )
            return 0
        if args.command == "import-otlp":
            if args.output.resolve() in (args.otlp.resolve(), args.policy_suite.resolve()):
                raise SuiteError("refusing to overwrite the source OTLP or policy suite")
            policy = load_suite(args.policy_suite)["policy"]
            suite = import_otlp(
                load_json_document(args.otlp),
                policy=policy,
                case_id=args.case_id,
                expected=args.expected,
            )
            _write_import_suite(args.output, suite, overwrite=args.overwrite)
            print(
                f"Imported {len(suite['cases'][0]['trace'])} tool spans. "
                "Label was user-provided, not independently verified. "
                "The output may contain sensitive arguments; review before sharing."
            )
            return 0
        if args.output and args.suite.resolve() == args.output.resolve():
            raise SuiteError("refusing to overwrite the input suite")
        report = evaluate_suite(load_suite(args.suite))
        if args.format == "json":
            display = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        else:
            counts = report["summary"]["confusion"]
            display = (
                f"Cases: {report['summary']['matched']}/{report['summary']['total']} matched\n"
                f"Confusion (deny=positive): TP={counts['tp']} TN={counts['tn']} "
                f"FP={counts['fp']} FN={counts['fn']}\n"
            )
            for case in report["cases"]:
                verdict = "PASS" if case["matched"] else "FAIL"
                codes = ",".join(v["code"] for v in case["violations"]) or "none"
                display += f"{verdict} {case['id']}: expected={case['expected']} actual={case['actual']} violations={codes}\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(display, encoding="utf-8")
        else:
            print(display, end="")
        return 0 if report["summary"]["matched"] == report["summary"]["total"] else 1
    except (SuiteError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
