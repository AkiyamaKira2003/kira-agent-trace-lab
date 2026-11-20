"""Command-line interface. Exit 0 = all expected verdicts matched; 1 = mismatch; 2 = input failure."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .engine import compare_policies, evaluate_suite
from .schema import SuiteError, load_json_document, load_suite
from .otlp import import_otlp
from .swe import import_swe_row
from .agentdojo import import_agentdojo_run
from .responses import import_responses_output, import_responses_sequence


def _write_complete_output(
    path: Path, payload: str, *, overwrite: bool, prefix: str,
) -> None:
    """Atomically publish complete UTF-8 content without implicit clobber."""
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
            prefix=prefix, suffix=".tmp", delete=False,
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


def _write_import_suite(path: Path, suite: dict, *, overwrite: bool) -> None:
    """Commit complete imported JSON with the existing safe-write contract."""
    payload = json.dumps(suite, indent=2, ensure_ascii=False) + "\n"
    _write_complete_output(
        path, payload, overwrite=overwrite, prefix=".agent-trace-import-",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-trace-lab", description="Offline policy audit of AI-agent tool traces")
    subcommands = parser.add_subparsers(dest="command", required=True)
    evaluate = subcommands.add_parser("evaluate", help="evaluate a JSON suite without executing its tool actions")
    evaluate.add_argument("suite", type=Path)
    evaluate.add_argument("--format", choices=("text", "json"), default="text")
    evaluate.add_argument("--output", type=Path, help="write complete report to a NEW file instead of stdout")
    evaluate.add_argument("--overwrite", action="store_true", help="explicitly replace an existing regular report file")
    evaluate.add_argument(
        "--summary-only", action="store_true",
        help="show only caller-labeled aggregate counts; omit case IDs, tools and violations",
    )
    compare = subcommands.add_parser(
        "compare-policies", help="compare policy-only decision deltas on identical offline trace cases",
    )
    compare.add_argument("suite", type=Path, help="validated baseline suite and recorded cases")
    compare.add_argument("--candidate-policy", type=Path, required=True,
                         help="JSON object containing schema_version and policy only")
    compare.add_argument("--format", choices=("text", "json"), default="text")
    compare.add_argument("--output", type=Path, help="write report to a NEW file instead of stdout")
    compare.add_argument("--overwrite", action="store_true", help="explicitly replace an existing regular report file")
    compare.add_argument(
        "--redact-case-ids", action="store_true",
        help="replace case IDs with deterministic per-report ordinals for sharing",
    )
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
    responses = subcommands.add_parser("import-responses", help="convert one completed OpenAI Responses API JSON output into an offline suite")
    responses.add_argument("response", type=Path, help="one locally saved response JSON object, not an event stream")
    responses.add_argument("--policy-suite", type=Path, required=True, help="validated suite providing the policy")
    responses.add_argument("--case-id", required=True, help="unique ID for the imported case")
    responses.add_argument("--expected", choices=("allow", "deny"), required=True, help="caller-supplied label, not inferred from model or tool output")
    responses.add_argument("--output", type=Path, required=True, help="private suite path (may include sensitive arguments)")
    responses.add_argument("--overwrite", action="store_true", help="explicitly replace an existing regular output file")
    sequence = subcommands.add_parser(
        "import-responses-sequence",
        help="convert a local ordered JSON array of completed Responses objects, without executing calls",
    )
    sequence.add_argument("responses", type=Path, help="app-authored JSON array of saved completed responses, NOT an API response envelope")
    sequence.add_argument("--policy-suite", type=Path, required=True, help="validated suite providing the policy")
    sequence.add_argument("--case-id", required=True, help="unique ID for the combined recorded case")
    sequence.add_argument("--expected", choices=("allow", "deny"), required=True, help="caller-supplied label, never independently authenticated")
    sequence.add_argument("--output", type=Path, required=True, help="private output suite path (may contain recorded arguments)")
    sequence.add_argument("--overwrite", action="store_true", help="explicitly replace an existing regular output")
    args = parser.parse_args(argv)
    try:
        if args.command == "import-responses-sequence":
            if args.output.resolve() in (args.responses.resolve(), args.policy_suite.resolve()):
                raise SuiteError("refusing to overwrite the response sequence or policy suite")
            suite = import_responses_sequence(
                load_json_document(args.responses),
                policy=load_suite(args.policy_suite)["policy"],
                case_id=args.case_id, expected=args.expected,
            )
            _write_import_suite(args.output, suite, overwrite=args.overwrite)
            print(
                f"Imported {len(suite['cases'][0]['trace'])} recorded function calls "
                "from a caller-ordered local response sequence. "
                "Label is caller-provided, not authenticated. "
                "No calls executed. Output may contain sensitive arguments."
            )
            return 0
        if args.command == "compare-policies":
            if args.output and args.output.resolve() in (
                args.suite.resolve(), args.candidate_policy.resolve(),
            ):
                raise SuiteError("refusing to overwrite baseline suite or candidate policy")
            report = compare_policies(
                load_suite(args.suite), load_json_document(args.candidate_policy),
                redact_case_ids=args.redact_case_ids,
            )
            if args.format == "json":
                display = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            else:
                counts = report["summary"]
                lines = [
                    f"Policy decisions changed: {counts['changed']}/{counts['total_cases']} "
                    f"(allow->deny={counts['allow_to_deny']}, "
                    f"deny->allow={counts['deny_to_allow']}). "
                    f"Candidate ignored grant records: {counts['candidate_ignored_grant_cases']}."
                ]
                for case in report["cases"]:
                    status = "CHANGED" if case["changed"] else "SAME"
                    lines.append(
                        f"{status} {case['id']}: "
                        f"baseline={case['baseline']} candidate={case['candidate']} "
                        f"baseline_codes={','.join(case['baseline_codes']) or 'none'} "
                        f"candidate_codes={','.join(case['candidate_codes']) or 'none'}"
                    )
                display = "\n".join(lines) + "\n"
            if args.output:
                try:
                    _write_complete_output(
                        args.output, display, overwrite=args.overwrite,
                        prefix=".agent-trace-compare-",
                    )
                except OSError as exc:
                    raise SuiteError("unable to safely write policy comparison report") from exc
            else:
                print(display, end="")
            return 0  # A policy difference is a result, not an execution failure.
        if args.command == "import-responses":
            if args.output.resolve() in (args.response.resolve(), args.policy_suite.resolve()):
                raise SuiteError("refusing to overwrite the response or policy suite")
            policy = load_suite(args.policy_suite)["policy"]
            suite = import_responses_output(
                load_json_document(args.response),
                policy=policy, case_id=args.case_id, expected=args.expected,
            )
            _write_import_suite(args.output, suite, overwrite=args.overwrite)
            print(
                f"Imported {len(suite['cases'][0]['trace'])} recorded Responses function calls. "
                "Label is caller-provided, not authenticated or inferred. "
                "No calls executed. Output may contain sensitive arguments."
            )
            return 0
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
        if args.summary_only:
            # Deliberately omit case records and derived accuracy/precision/
            # recall to avoid misrepresenting caller labels as independent
            # security ground truth in a shareable aggregate-only report.
            totals = report["summary"]
            counts = totals["confusion"]
            if args.format == "json":
                display = json.dumps({
                    "schema_version": report["schema_version"],
                    "label_basis": "caller_supplied_not_independently_verified",
                    "verified_real_world_security_metrics": False,
                    "summary": {
                        "total_cases": totals["total"],
                        "matched_fixture_labels": totals["matched"],
                        "mismatched_fixture_labels": totals["total"] - totals["matched"],
                        "confusion": counts,
                    },
                }, indent=2, ensure_ascii=False) + "\n"
            else:
                display = (
                    f"Caller-supplied fixture labels matched: {totals['matched']}/{totals['total']}\n"
                    f"Caller-label confusion (deny=positive): TP={counts['tp']} "
                    f"TN={counts['tn']} FP={counts['fp']} FN={counts['fn']}\n"
                    "No independently verified real-world security metrics.\n"
                )
        elif args.format == "json":
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
            try:
                _write_complete_output(
                    args.output, display, overwrite=args.overwrite,
                    prefix=".agent-trace-report-",
                )
            except OSError as exc:
                # Destination names can reveal private case/client data.
                raise SuiteError("unable to safely write evaluation report") from exc
        else:
            print(display, end="")
        return 0 if report["summary"]["matched"] == report["summary"]["total"] else 1
    except (SuiteError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
