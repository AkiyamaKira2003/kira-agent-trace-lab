"""Command-line interface. Exit 0 = all expected verdicts matched; 1 = mismatch; 2 = input failure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import evaluate_suite
from .schema import SuiteError, load_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-trace-lab", description="Offline policy audit of AI-agent tool traces")
    subcommands = parser.add_subparsers(dest="command", required=True)
    evaluate = subcommands.add_parser("evaluate", help="evaluate a JSON suite without executing its tool actions")
    evaluate.add_argument("suite", type=Path)
    evaluate.add_argument("--format", choices=("text", "json"), default="text")
    evaluate.add_argument("--output", type=Path, help="write report to file instead of stdout")
    args = parser.parse_args(argv)
    try:
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
