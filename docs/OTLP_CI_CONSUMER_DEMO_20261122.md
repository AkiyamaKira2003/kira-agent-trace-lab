# ATL-004DP — copyable offline OTLP policy audit CI consumer

**Status:** self-authored synthetic developer workflow proof, not a production security release.

## Why a separate consumer check?

The unit tests for `audit-otlp` already verify the exit status contract.
This example drives the real CLI in separate Python subprocesses the same
way a downstream CI consumer does, without relying on test internals.
It is also a small cross-platform example for Windows and Ubuntu CI.

Run from this checkout (Python 3.10+; no API key, DAW, agent or paid service):

```sh
python -m scripts.verify_otlp_ci_consumer
```

Copy this step into a Python-matrix job of `.github/workflows/test.yml`
**in this repository** after `actions/checkout` and `actions/setup-python`:

```yaml
- name: Offline OTLP policy gate (synthetic only)
  run: python -m scripts.verify_otlp_ci_consumer
```

For a **different** repository, copy the original example policy/trace and
the standalone `scripts/verify_otlp_ci_consumer.py` test driver, or adapt
the real CLI invocation below to **your own** safely stored local trace
and policy. Do not silently assume that other repositories contain these
fixture paths:

```sh
python -m agent_trace_lab audit-otlp examples/otlp_spans.json --policy-file examples/otlp_audit_policy.json --fail-on-deny
```

The script creates a disposable stricter policy (`max_actions=1`) from the
sample that has two recorded calls, and a disposable malformed JSON file.
It runs subprocesses, asserts valid allow=**0**, default deny=**0**,
opt-in deny=**1**, malformed=**2**, verifies identical deny report bodies
with/without the flag and checks that explicit nonclaims remain `false`.
It prints only a bounded pass/fail summary. Scratch files are removed when
the process exits normally, no report artifact is written or uploaded, and
**no recorded tool call is executed**. It uses Python standard library only.

**Safety interpretation:** exit 0 or 1 is a locally computed policy decision
about the *observed* spans. It cannot prove that all OTLP HTTP POST batches
were captured, that a human authorized any action, that omitted calls do
not exist, or that a denial represents malicious intent. Exit 2 indicates
invalid input, not a security finding. Never upload real private agent
arguments/traces to public CI artifacts or infer detection metrics from
these synthetic examples. Real customer value and independent security
acceptance remain unverified.
