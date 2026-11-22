# ATL-004DQ — evidence-first developer adoption gate

**Date:** 2026-11-22. **Decision:** `NO_GO_NEW_FEATURE / HOLD_USER_EVIDENCE`.
This is a targeted source/competitor review and an original synthetic negative
control, **not** a user study, market-size estimate, deployment or new release.

## One specific developer job worth checking

An agent developer has a *locally saved* OTLP trace, but observability settings
have deliberately omitted `gen_ai.tool.call.arguments` to protect private data.
They want a CI check of the **actual** recorded action against a path/host
policy without uploading private arguments or inventing authorization. The
critical question is whether a tool-argument-dependent policy can return a
meaningful verdict with only partial trace evidence.

### Dated public evidence (linked source claims, not local replications)

1. The official [OpenTelemetry GenAI execute-tool convention](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/execute-tool.md)
   marks recorded tool call arguments as sensitive/opt-in. The
   [official November 2026 OTel walkthrough](https://github.com/open-telemetry/opentelemetry.io/blob/main/content/en/blog/2026/genai-observability/index.md)
   explains that content capture is normally off to avoid collecting private
   prompt/tool content. Missing arguments are therefore a realistic scenario,
   not by themselves evidence of a broken exporter.
2. [OpenTelemetry proposal #402](https://github.com/open-telemetry/semantic-conventions-genai/issues/402)
   describes the need for privacy-preserving tool argument correlation, with
   proposed hashes instead of raw data. This is an **upstream proposal**,
   not proof that hashes permit a path/host allowlist decision, an adopted
   spec, or demand for this particular CLI.
3. [Langfuse documentation issue #4188](https://github.com/langfuse/langfuse-docs/issues/4188)
   (opened 2026-11-01) asks how OTEL span filtering and required root spans
   interact. It is evidence of a real *documentation/completeness question*,
   not a user request for Agent Trace Lab or a proven loss in our importer.
4. Mature alternative [Arize Phoenix CLI](https://github.com/Arize-ai/phoenix/blob/main/docs/phoenix/tracing/how-to-tracing/importing-and-exporting-traces/retrieve-traces-via-cli.mdx)
   already retrieves/export traces as JSON for offline analysis and CLI
   automation. [Langfuse](https://langfuse.com/docs) also provides
   OTel-based trace analysis and evaluations. We have **not** proved that
   either lacks custom deterministic checks, nor run their products locally.
   Do not compete by cloning a generic trace viewer or exporter.

## Separately executed synthetic negative control on KIRAA

The only generated material is self-authored example JSON, stored in ignored
`artifacts/atl004dq_external_job_probe_20261122/`. It starts from the existing
`examples/otlp_spans.json` and removes only the recorded-arguments attribute
from one `execute_tool` span; an unrelated synthetic private marker checks
that diagnostics do not echo arbitrary trace values.

Re-run on any supported Python 3.10+ host from the repository checkout:

```sh
python -m scripts.reproduce_otlp_missing_args
```

The original ignored exploratory harness and `receipt.json` were actually
executed on 2026-11-22 at clean `main` SHA
`86746279294ef812ba25b2be7df8f544b41752b5`.
The checked-in reproduction script provides the same standalone test to
future readers; its generated JSON/receipt remain ignored, not released.
Generated missing-argument JSON SHA-256:
`cca6cf36b85b9740a188fc977925d2dbba735d7cd4675c45a0dacff187884f80`.
Observed baseline: `allow`, exit **0**, with
`trace_completeness_verified=false`. Observed missing-argument trace:
exit **2**, **empty stdout**, no Python traceback, and no synthetic private
marker in stderr. Source `agent_trace_lab/otlp.py:128-130` deliberately
raises `SuiteError` on omitted opt-in arguments; an existing test in
`tests/test_otlp_policy_audit.py` already covers this case.

**Conclusion:** the source already rejects the unsafe case. Treating a
missing argument as `{}`, a harmless action, or a trusted hash would be
**unsound** for argument-dependent policies. This is a verified fail-closed
behavior, **not** a discovered bug. The fixture is synthetic; actual exporters,
other argument types, real users and backend completeness were not tested.

## Decision and consent-ready validation protocol

**NO GO** for a new parser mode, a metadata-only `allow` verdict, a
completeness certificate, a generic telemetry viewer, or another repository.
There is no confirmed independent developer requesting the specific feature,
no representative anonymized trace, no demonstrated gap the current fail-closed
behavior fails to handle, and no head-to-head competing implementation test.
Do not mistake one upstream proposal or documentation question for product
adoption. No new source functionality, tests or CI jobs are warranted.

For a developer **who voluntarily opts in**, ask *without collecting raw
private traces or API keys*:

1. Which actual framework/export path and tool family do you use, and what
   decision must your CI gate make?
2. Are tool arguments intentionally absent/redacted? Can you safely generate
   an **original synthetic equivalent** instead of sharing production data?
3. Is fail-closed exit 2 usable today? If not, give an exact command,
   expected exit/report and practical consequence **without private values**.
4. What existing Phoenix/Langfuse/custom-policy process do you use, and what
   reproducible step makes it inadequate?

Only after an explicitly consented and independently reproducible user job:
compare an equivalent synthetic case with mature alternatives; identify the
smallest specific unhandled contract; define privacy/security acceptance tests;
and seek owner authorization before implementing a bounded feature. No cold
outreach, uploads, simulated endorsements, fabricated demand, telemetry
collection or irreversible publication.

**Release:** production security HOLD. The existing offline CLI cannot
authenticate trace capture closure, human grants, observed side effects or
real-world security metrics. The project remains a research prototype.
