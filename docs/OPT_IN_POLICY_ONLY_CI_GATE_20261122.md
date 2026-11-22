# ATL-004DO — opt-in CI exit status for policy-only OTLP audit

**Status:** bounded self-authored offline CLI proof; no new security claims.
This is a small follow-up to the completed label-free
[OTLP policy audit](LABEL_FREE_OTLP_POLICY_AUDIT_20261122.md).

## Reproducible issue

Before this change, a valid policy `deny` returned exit code 0 by design
(the command was for *inspection*). In a CI workflow, a pipeline must
parse the JSON body to fail on that policy finding. An optional
`--fail-on-deny` provides a simple status contract **without** changing
the existing default.

| Outcome | Default exit | With `--fail-on-deny` |
| --- | ---: | ---: |
| Valid trace, policy `allow` | 0 | 0 |
| Valid trace, policy `deny` | 0 | 1 |
| Invalid JSON, OTLP span/ID or policy | 2 | 2 |

The status code depends on the existing deterministic policy verdict,
**not** an expected-label match, threat-detection metric or verified
human consent. Both valid outcomes still print the **same** privacy-limited
JSON/text report, with false values for ground truth, authorization,
security metrics, trace completeness and recorded tool execution. The flag
does not read or write report files or execute recorded actions.

## Local synthetic reproduction

Run from the repository root:

```powershell
# Default and opt-in allow both return exit 0.
python -m agent_trace_lab audit-otlp examples/otlp_spans.json --policy-file examples/otlp_audit_policy.json --fail-on-deny
$LASTEXITCODE
```

For the deny example, copy the example policy into a **private temporary
directory** and change only `policy.max_actions` from 3 to 1. The same
recorded sample has two tool calls, so the policy-only report is `deny`
with an `ACTION_LIMIT_EXCEEDED` code at event index 1. The default
command exits 0, while `--fail-on-deny` exits 1 **without changing output**.
Do not commit real tool traces, arguments, credentials or customer logs.

## Evidence and boundaries

The new regression tests in `tests/test_otlp_policy_audit.py` verify
allow=0, default deny=0, opt-in deny=1, invalid=2, JSON/text parity,
synthetic sensitive-argument redaction, no fake `expected` labels or
partial report files. Installed-wheel smoke additionally tests actual
console/module behavior in an isolated target. Re-run:

```powershell
python -m unittest tests.test_otlp_policy_audit -q
python -m unittest discover -s tests -q
python -m compileall -q agent_trace_lab scripts tests
```

This makes CI automation more convenient; it does **not** prove actual
developer adoption or that all HTTP POST batches were received. A
policy `allow` is not independently verified security, and a policy
`deny` is not proof of a real malicious act. Production security
release remains HOLD pending external evidence and review.

**Verified local execution (KIRAA, 2026-11-22):** a controlled, Git-ignored
synthetic policy restricted `max_actions=1` for a two-action trace.
Default audit returned `deny` and exit 0; the flag returned the
**byte-identical** report and exit 1. Focused tests: 84 PASS.
Full suite: 437 discovered, 433 PASS and 4 existing Windows-environment
SKIP. Python compileall and whitespace/credential-pattern checks passed.
The research-only source wheel `0.5.0.dev2` (40,332 bytes, SHA-256
`762a37654668d25e3b53fad02980b6155c79e7a76379753c7b0ea6516217a3f7`)
was built without index/dependency fetching and passed isolated installed
module/console, legacy workflow, package-boundary and CI-gate smoke.
The wheel and temporary proof files remain in Git-ignored `artifacts/`.
These are **local self-checks**; an independent security review and
production safety validation were not performed.
