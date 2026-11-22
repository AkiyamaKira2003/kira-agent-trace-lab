# ATL-004DN — unlabeled OTLP policy-only CLI, bounded synthetic proof

**Scope:** This is a source implementation and self-reviewed local test of
[issue #72](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/72).
It addresses the verified **developer UX** issue from
[ATL-004DM](PRODUCT_VALUE_TRIAGE_20261122.md); there is no verified user
adoption, independently authenticated authorization, or agent safety evidence.

## Reproducible, offline quick start

Run from the source checkout (Python 3.10+, standard library only):

```sh
python -m agent_trace_lab audit-otlp examples/otlp_spans.json --policy-file examples/otlp_audit_policy.json
python -m agent_trace_lab audit-otlp examples/otlp_spans.json --policy-file examples/otlp_audit_policy.json --format text
```

The self-authored sample contains two recorded `execute_tool` spans from a
single synthetic trace. The policy-only JSON has exactly
`{"schema_version": "1.0", "policy": {...}}`, with **no expected label**.
The policy scan uses the same code path as labeled suite evaluation but
returns only a policy verdict and fixed reason codes/event positions.
Malformed OTLP, no recorded tool calls, repeated or mixed IDs, missing
tool arguments, missing timestamps, invalid policy fields and malformed
JSON are rejected (exit 2). Valid `allow` and `deny` verdicts both return
exit 0, since a denial is a finding, not a failure to parse.
An optional `--fail-on-deny` flag changes valid-deny exit to 1 for CI
without changing the JSON/text body, label provenance or incomplete-capture
limitations; see [ATL-004DO](OPT_IN_POLICY_ONLY_CI_GATE_20261122.md).

The output always marks `ground_truth_available=false`,
`user_authorization_verified=false`, `security_metrics_available=false`,
`trace_completeness_verified=false`, and
`recorded_actions_executed=false`. It contains no expected labels,
confusion matrix, accuracy, precision/recall, tool argument values or
recorded tool names. Event indexes and fixed violation codes still expose
some workflow structure and should be treated appropriately.

For schema 1.1, the saved `policy` file must declare
`task_guarded_tools`; without independently verified grants, guarded
calls **deny** with a `TASK_GRANT_REQUIRED` code. This CLI does not ingest
or manufacture grant records. No saved suite with an invented `expected`
label is constructed even internally. Labeled `import-otlp` and
`evaluate` workflows retain their existing contracts.

## Security and product limits

- The input is *one complete, saved* OTLP/HTTP JSON envelope as **declared by
  the caller**. Prior [two-POST research](OTLP_MULTI_POST_COMPLETENESS_20261122.md)
  proved one valid envelope can omit later tool calls. This audit cannot
  detect missing batches or authenticate trace closure.
- Tool calls are **never replayed**, and the program sends no network traffic.
  Tool argument values may contain secrets in the locally saved OTLP source;
  do not upload those files or interpret the output as anonymized input.
- It does not prove a human authorized the trace, whether the policy is
  appropriate, or whether an observed tool action caused a real side effect.
  A policy `allow` is not a verified safety/consent result.
- Existing private human-grant source review, independent reviewers, and
  representative externally labeled outcomes remain prerequisites for
  any qualified security-product release. No KiraShop site change, tag,
  production collector or external service is part of this task.

## Test evidence

Automated self-authored regression cases reside in
`tests/test_otlp_policy_audit.py`: label-free positive/negative verdicts,
guarded-call denial, scoped-path rejection, malformed/replayed/mixed spans,
privacy of synthetic markers, deterministic JSON, explicit text disclaimers
and unchanged legacy mandatory-label behavior. They also compare the same
policy verdict against the legacy labeled engine without retaining
any label in the policy-only output. Verify:

```sh
python -m unittest tests.test_otlp_policy_audit tests.test_otlp tests.test_task_grants -q
python -m unittest discover -s tests -q
python -m compileall -q agent_trace_lab scripts tests
```

These are synthetic local correctness checks and must not be described as
independent penetration testing, user authorization verification, market
demand proof or cross-system trace completeness.

**Local package evidence (KIRAA):** A source-dev2 pure-Python wheel was built
with `python -m pip wheel --no-deps --no-build-isolation --no-index` into
Git-ignored `artifacts/atl004dn_policy_only_wheel_20261122/`. Wheel
`kira_agent_trace_lab-0.5.0.dev2-py3-none-any.whl` was **40,077 bytes**,
SHA-256 `6dcbada07ffd554f3da1bcef0aad0d62c30b8024d425dfe753c03e9c27399449`.
The isolated installed-wheel smoke returned
`ISOLATED_INSTALLED_WHEEL_SMOKE_PASS`, verifying module/console parity,
policy-only CLI privacy/nonclaims, legacy imports, offline installation,
packaging boundary, license and no extra runtime dependency. This is
**local research-only package validation**, not a GitHub v0.5 release.
