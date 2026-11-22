# ATL-004DM — product-value triage: policy verdicts for unlabeled agent traces

**Date:** 2026-11-22. **Decision:** one *technically verified workflow gap*; **user demand not validated**. Scope: read-only comparison of existing source, one controlled local reproduction, public upstream docs, and the existing GitHub issue backlog. No runtime code changes, real user data, outside instrumentation or new product repository.

## User job and who might need it

Hypothetical user: a developer or CI maintainer who has a locally saved OpenTelemetry agent tool-call trace, and wants to ask, **“Under my proposed policy, which recorded actions would be allowed or denied, and why?”** The developer has **not** collected independently reviewed allow/deny ground-truth labels. They need a deterministic, offline **policy decision** before anyone can make claims about consent, malicious intent or security effectiveness.

This is a plausible job, not an interview-backed demand, usage metric, market-size estimate or evidence of willingness to adopt. A next phase should obtain consented developer feedback or a credible issue/report from an actual user before declaring product-market fit.

## Actual source contracts and one reproduced point of friction

- Current CLI has `evaluate`, `validate`, `compare-policies` and five import subcommands, but **no one-step unlabeled policy-only trace audit** (`agent_trace_lab/cli.py`, lines 63–137). `validate` checks structure, not policy. `compare-policies` compares two policies on **already labeled suite cases**; it intentionally avoids security accuracy metrics but requires a prepared suite.
- `import-otlp` **requires** `--expected allow|deny` and a writable `--output` destination (`agent_trace_lab/cli.py`, lines 100–105, 291–307). The other import adapters also ask for a caller-supplied expected label. The importer always constructs a labeled suite (`agent_trace_lab/otlp.py`, lines 97–179).
- Reproduced locally on KIRAA at clean `main` `292b60d987ec188ffb8d027cc24366f7692acbeb`: `python -m agent_trace_lab import-otlp examples/otlp_spans.json --policy-suite examples/suite.json --case-id synthetic_unlabeled --output artifacts/atl004dm_must_not_exist.json` without `--expected` returned **exit 2**, and **no destination file** was created. This is *intended interface behavior*, not a parser/security bug.
- Separate controlled test used the **same** source sample (SHA256 `4767a5652e69cc044be4ea0e911d513d8a7aff550df143704edd75fd58e669ec`) to import twice with caller-provided `--expected allow` and `--expected deny`, then `evaluate --summary-only --format json`. With only the supplied label changed, the output changed from **1/1 matched, TN=1** to **0/1 matched, FN=1**. Both already disclose `label_basis=caller_supplied_not_independently_verified` and `verified_real_world_security_metrics=false`. Thus the tool correctly warns, but forces an unnecessary label choice for a policy-only user job.
- Both generated synthetic suites were retained **only** in Git-ignored `artifacts/atl004dm_value_triage_20261122/`; no source files, external apps, user traces, grants or protected checkouts were changed. An existing repo [issue #14](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/14) separately tracks independent authorization labels. It must **not** be solved by silently inventing labels.

## Two mature alternatives (official public sources checked 2026-11-22)

| Alternative and primary sources | Verified public capability | Consequence for this lab |
| --- | --- | --- |
| [Arize Phoenix overview](https://github.com/Arize-ai/phoenix/blob/main/docs/phoenix.mdx), [GitHub](https://github.com/Arize-ai/phoenix) | Open-source/self-hostable OTLP-based tracing with a UI, framework integrations, LLM/code/human evaluations, datasets, experiments and span replay | Do **not** duplicate a generic trace viewer, ingestion platform, prompt playground or LLM evaluation stack. |
| [Langfuse overview](https://github.com/langfuse/langfuse-docs/blob/main/content/docs/index.mdx), [capability clarifications](https://langfuse.com/resources/engineering/clarifications), [OTLP API](https://langfuse.com/docs/api-and-data-platform/features/public-api) | Self-hostable, OpenTelemetry ingestion, tracing/sessions, prompt management, code and LLM evaluators, annotations, datasets, experiments and CI support | Do **not** claim Langfuse lacks deterministic code evaluation or CI. Full platforms are real alternatives; being smaller alone is not defensible differentiation. |

**Unverified competitor detail:** These sources do *not* establish that neither product can run an equivalent policy check through custom code or integrations. No head-to-head benchmark, cost benchmark or user preference test was conducted. Product differentiation remains a **hypothesis**: a standalone **Python-standard-library-only, offline, no-label-needed, deterministic, policy-only CLI**, with no collector, DB, API key or hosted service, would prioritize a much narrower developer task than full observability.

## ONE selected issue — unlabeled OTLP policy dry-run

**Tracked:** [issue #72 — unlabeled OTLP policy-only dry run](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/72). **Proposal:** an opt-in CLI workflow for *one complete, saved* OTLP JSON trace plus a locally supplied validated policy. Print only policy verdicts and bounded, privacy-aware reason codes **without asking for any expected label** or creating a labeled suite/report that implies human approval.

**Acceptance requirements for a bounded follow-up:**

1. RED test: existing CLI fails the one-command unlabeled workflow, even though `import_otlp` can parse the input when an artificial label is supplied. No new repo; keep source-only synthetic fixtures.
2. Implement a **minimal** independent policy-only workflow on the existing OTLP parser/engine, not a second collector or parser. Do not fabricate `expected` even internally if a straightforward pure parsing/evaluation path is available; avoid breaking existing labeled importers.
3. Deterministic output: `actual=allow|deny`, action count and bounded violation codes/indexes; explicit `ground_truth_available=false`, `user_authorization_verified=false`, `security_metrics_available=false`. **No** TP/TN/FP/FN, accuracy, recall or arbitrary argument values.
4. Same sample must produce a stable policy verdict **without** `--expected`; a different caller label must be irrelevant. Invalid IDs, missing arguments, mixed traces, duplicate spans, malformed JSON and truncated OTLP captures remain fail-closed. Full test suite, Windows/Linux CI, package/README quality and non-leaking stderr must stay green.
5. Work on a single permitted repo, `kira-agent-trace-lab`, with no live agent, paid API, automatic execution, deployment, KiraShop changes or security-product release. Evaluate usefulness with real users **after** an honest synthetic demo, not by inventing traction.

**Go/no-go:** Proceed to a bounded RED/GREEN *prototype* because the workflow gap was reproduced. **HOLD** any claim of verified demand, independent real-user consent, authenticated trace completeness, competitive superiority or production safety. If minimal design would require broad schema incompatibility, stop with a failed-acceptance report and do not bolt a fake `expected` field onto a production security output.
