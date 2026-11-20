# Changelog

## v0.4.0 — 2026-11-20

- Experimental, offline import of SWE-agent-style **single-row** recorded assistant tool calls with strict JSON arguments and bounded input. The importer is available in this stable *package release*, but the importer format remains an experimental integration.
- Ignore model thoughts, tool outputs and task-success labels when producing the action suite. Never execute imported tools or infer grants.
- Source-format validation progressed beyond the initial HTTP 502/timeout: one recorded NVIDIA Open-SWE-Traces benchmark run (97 messages and 48 calls) imported successfully from an externally retrieved first-row preview. Relevant identity, message-role and exact action-argument fields were independently reproduced from the matching revision-pinned source Parquet shard using bounded HTTP byte ranges.
- Optional source-audit scripts check the dataset server's revision header and reproduce the pinned Parquet action fields without executing the calls; PyArrow is optional and **not** a runtime dependency.
- 79 local unit tests and GitHub CI on Windows and Ubuntu with Python 3.10 and 3.12. Input/source content and human authorization labels remain separate verification questions.
- **Limits:** no independently labeled real-user authorization corpus or representative AI-agent security benchmark; no proof of complete conversation-row byte equality, approval authenticity or runtime enforcement. No accuracy or safety claims are implied by the reported synthetic fixture scores.

## v0.3.0 — 2026-11-20

- Attributed external AgentDrift **synthetic** action-case adaptation under CC BY 4.0.
- Regression test deliberately demonstrates task-authorization blind spots: one benign match and one hijacked mismatch under a permissive tool-name policy. This is a two-case case study, not a model-safety benchmark.
- Added opt-in schema 1.1 with exact-action, single-use task grants and default-deny behavior for named guarded tools.
- Kept schema 1.0 unchanged; compatible offline OpenTelemetry import remains untrusted and does not manufacture grants.
- Added explicit authorization threat-model ADR, fixture-based CLI smoke tests and negative controls.

## v0.2.0 — 2026-11-20

- Read-only importer for a limited OTLP/HTTP JSON execute_tool span format.
- Required explicit human label, tool name, captured arguments, trace ID and timestamp.
- Strict refusal to merge multiple traces or silently infer missing tool arguments.
- Additional import tests and CI smoke test.

## v0.1.0 — 2026-11-20

- Deterministic allow/deny policy engine, strict bounded JSON suite, stdlib CLI.
- Synthetic safe and adversarial fixtures, 16 initial unit tests.
- Python wheel build and four-platform-version CI matrix passed.

These releases describe software functionality, not a measured AI model-safety result.
