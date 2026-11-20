"""Static trace evaluator; deliberately performs no filesystem or network actions."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from .schema import _exact_arguments, validate_suite


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
