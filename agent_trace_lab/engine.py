"""Static trace evaluator; deliberately performs no filesystem or network actions."""

from __future__ import annotations

import copy
from typing import Any
from urllib.parse import urlsplit

from .schema import _exact_arguments, _keys, validate_suite


def _path_permitted(value: Any, roots: list[str]) -> tuple[bool, str]:
    if not isinstance(value, str) or not value or not value.startswith("/") or value.startswith("//"):
        return False, "PATH_INVALID"
    if "\\" in value or "\x00" in value or any(p in (".", "..", "") for p in value.split("/")[1:]):
        return False, "PATH_INVALID"
    if any(root == "/" or value == root or value.startswith(root + "/") for root in roots):
        return True, ""
    return False, "PATH_OUTSIDE_ROOT"


def _url_permitted(value: Any, hosts: list[str]) -> tuple[bool, str]:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value) or "\\" in value:
        return False, "URL_INVALID"
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or not parsed.hostname
        ):
            return False, "URL_INVALID"
    except ValueError:
        return False, "URL_INVALID"
    if parsed.hostname.lower() not in hosts:
        return False, "HOST_NOT_ALLOWED"
    return True, ""


def _violation(index: int, tool: str, code: str, argument: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"event_index": index, "tool": tool, "code": code}
    if argument is not None:
        result["argument"] = argument
    return result


def evaluate_suite(suite: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic verdicts; positive class is expected='deny'."""
    validate_suite(suite)
    policy = suite["policy"]
    guarded = set(policy.get("task_guarded_tools", []))
    results: list[dict[str, Any]] = []
    tp = tn = fp = fn = 0
    for case in suite["cases"]:
        violations: list[dict[str, Any]] = []
        authorization = case.get("task_authorization") or {}
        grants = authorization.get("grants", [])
        consumed: set[str] = set()
        for index, event in enumerate(case["trace"]):
            name, args = event["tool"], event["arguments"]
            if index >= policy["max_actions"]:
                violations.append(_violation(index, name, "ACTION_LIMIT_EXCEEDED"))
            config = policy["tools"].get(name)
            if config is None:
                violations.append(_violation(index, name, "TOOL_NOT_ALLOWED"))
                continue
            for arg in config.get("path_args", []):
                if arg not in args:
                    violations.append(_violation(index, name, "MISSING_ARGUMENT", arg))
                    continue
                allowed, code = _path_permitted(args[arg], config["allowed_roots"])
                if not allowed:
                    violations.append(_violation(index, name, code, arg))
            for arg in config.get("url_args", []):
                if arg not in args:
                    violations.append(_violation(index, name, "MISSING_ARGUMENT", arg))
                    continue
                allowed, code = _url_permitted(args[arg], config["allowed_hosts"])
                if not allowed:
                    violations.append(_violation(index, name, code, arg))
            if name in guarded:
                observed = _exact_arguments(args, f"cases[{case['id']}].trace[{index}].arguments")
                matched_grant = next(
                    (
                        grant for grant in grants
                        if grant["grant_id"] not in consumed
                        and grant["tool"] == name
                        and _exact_arguments(grant["arguments"], f"grants[{grant['grant_id']}].arguments")
                        == observed
                    ),
                    None,
                )
                if matched_grant is None:
                    violations.append(_violation(index, name, "TASK_GRANT_REQUIRED"))
                else:
                    consumed.add(matched_grant["grant_id"])
        actual = "deny" if violations else "allow"
        expected = case["expected"]
        if expected == "deny" and actual == "deny":
            tp += 1
        elif expected == "allow" and actual == "allow":
            tn += 1
        elif expected == "allow":
            fp += 1
        else:
            fn += 1
        results.append({
            "id": case["id"],
            "expected": expected,
            "actual": actual,
            "matched": actual == expected,
            "violations": violations,
        })
    total = len(results)
    return {
        "schema_version": suite["schema_version"],
        "summary": {
            "total": total,
            "matched": tp + tn,
            "accuracy": (tp + tn) / total,
            "deny_precision": tp / (tp + fp) if tp + fp else None,
            "deny_recall": tp / (tp + fn) if tp + fn else None,
            "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        },
        "cases": results,
    }


_MAX_WITNESS_CASES = 5
_MAX_WITNESS_EVENTS = 64
_MAX_WITNESS_EVALUATIONS = 128


def _policy_delta_witness(
    case: dict[str, Any],
    baseline_version: str,
    baseline_policy: dict[str, Any],
    candidate_version: str,
    candidate_policy: dict[str, Any],
    expected_pair: tuple[str, str],
) -> dict[str, Any]:
    """Shrink a changed policy verdict to a 1-minimal ordered subsequence.

    This is *not* a causal execution trace. Each probe evaluates recorded
    metadata without calling a tool, and the public result has indexes only.
    The bounded search never calls an incomplete witness 'minimal'.
    """
    original = case["trace"]
    retained = list(range(len(original)))
    evaluations = 0
    while True:
        removed_any = False
        for position in range(len(retained) - 1, -1, -1):
            if evaluations >= _MAX_WITNESS_EVALUATIONS:
                return {
                    "status": "budget_exhausted",
                    "event_indexes": retained,
                    "evaluations": evaluations,
                }
            trial_indexes = retained[:position] + retained[position + 1:]
            trial = {**case, "trace": [original[index] for index in trial_indexes]}
            baseline_result = evaluate_suite({
                "schema_version": baseline_version,
                "policy": baseline_policy,
                "cases": [trial],
            })["cases"][0]["actual"]
            candidate_trial = dict(trial)
            if candidate_version == "1.0":
                candidate_trial.pop("task_authorization", None)
            candidate_result = evaluate_suite({
                "schema_version": candidate_version,
                "policy": candidate_policy,
                "cases": [candidate_trial],
            })["cases"][0]["actual"]
            evaluations += 1
            if (baseline_result, candidate_result) == expected_pair:
                retained = trial_indexes
                removed_any = True
        if not removed_any:
            return {
                "status": "one_minimal",
                "event_indexes": retained,
                "evaluations": evaluations,
            }


def compare_policies(
    baseline_suite: dict[str, Any], candidate_document: dict[str, Any],
    *, redact_case_ids: bool = False, minimal_witness: bool = False,
) -> dict[str, Any]:
    """Compare decisions for identical recorded cases without trusting labels.

    The candidate document contains only a schema_version and a policy.
    Expected case labels never influence the comparison. No raw arguments,
    tool names or grant evidence are included in the result.
    """
    if type(redact_case_ids) is not bool:
        raise ValueError("redact_case_ids must be a boolean")
    if type(minimal_witness) is not bool:
        raise ValueError("minimal_witness must be a boolean")
    if redact_case_ids:
        # Validate before replacing IDs, so malformed input never becomes
        # valid through rewriting. Evaluate only aliases, including on
        # error paths in guarded tool argument validation.
        validate_suite(baseline_suite)
        source_suite = copy.deepcopy(baseline_suite)
        for index, case in enumerate(source_suite["cases"]):
            case["id"] = f"case_{index + 1:04d}"
    else:
        source_suite = baseline_suite
    before = evaluate_suite(source_suite)
    candidate_document = _keys(
        candidate_document, "candidate_policy", {"schema_version", "policy"},
    )
    candidate_version = candidate_document["schema_version"]
    candidate_policy = candidate_document["policy"]
    validate_suite({
        "schema_version": candidate_version,
        "policy": candidate_policy,
        "cases": [{"id": "candidate_schema_check", "expected": "allow", "trace": []}],
    })
    candidate_cases = copy.deepcopy(source_suite["cases"])
    ignored_grants = 0
    if candidate_version == "1.0":
        # Schema 1.0 does not understand grants. Make the loss explicit
        # instead of silently pretending the candidate used those records.
        for case in candidate_cases:
            if "task_authorization" in case:
                del case["task_authorization"]
                ignored_grants += 1
    after = evaluate_suite({
        "schema_version": candidate_version,
        "policy": candidate_policy,
        "cases": candidate_cases,
    })
    changed = allow_to_deny = deny_to_allow = 0
    witnessed_cases = 0
    cases: list[dict[str, Any]] = []
    for case_data, original, proposed in zip(
        source_suite["cases"], before["cases"], after["cases"],
    ):
        prior = original["actual"]
        later = proposed["actual"]
        is_changed = prior != later
        if is_changed:
            changed += 1
            if prior == "allow":
                allow_to_deny += 1
            else:
                deny_to_allow += 1
        row = {
            "id": original["id"],
            "baseline": prior,
            "candidate": later,
            "changed": is_changed,
            "baseline_codes": sorted({item["code"] for item in original["violations"]}),
            "candidate_codes": sorted({item["code"] for item in proposed["violations"]}),
        }
        if minimal_witness:
            if not is_changed:
                row["witness"] = None
            elif witnessed_cases >= _MAX_WITNESS_CASES:
                row["witness"] = {
                    "status": "skipped_case_limit",
                    "event_indexes": None,
                    "evaluations": 0,
                }
            else:
                witnessed_cases += 1
                if len(case_data["trace"]) > _MAX_WITNESS_EVENTS:
                    row["witness"] = {
                        "status": "skipped_trace_limit",
                        "event_indexes": None,
                        "evaluations": 0,
                    }
                else:
                    row["witness"] = _policy_delta_witness(
                        case_data, source_suite["schema_version"], source_suite["policy"],
                        candidate_version, candidate_policy, (prior, later),
                    )
        cases.append(row)
    return {
        "baseline_schema_version": source_suite["schema_version"],
        "candidate_schema_version": candidate_version,
        "summary": {
            "total_cases": len(cases),
            "changed": changed,
            "allow_to_deny": allow_to_deny,
            "deny_to_allow": deny_to_allow,
            "unchanged": len(cases) - changed,
            "candidate_ignored_grant_cases": ignored_grants,
        },
        "cases": cases,
    }
