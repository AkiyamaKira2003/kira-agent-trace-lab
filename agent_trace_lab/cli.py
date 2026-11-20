"""Command-line interface. Exit 0 = all expected verdicts matched; 1 = mismatch; 2 = input failure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import evaluate_suite
from .schema import SuiteError, load_json_document, load_suite
from .otlp import import_otlp


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
    args = parser.parse_args(argv)
    try:
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
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(suite, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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
