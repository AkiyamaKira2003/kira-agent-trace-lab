# Changelog

## Unreleased (v0.4.0.dev0)

- Experimental, offline import of SWE-agent-style **single-row** recorded assistant tool calls with strict JSON arguments and bounded input.
- Ignore model thoughts, tool outputs and task-success labels when producing the action suite. Never execute imported tools or infer grants.
- Synthetic structural tests and CLI smoke test. Raw NVIDIA dataset compatibility is not fully verified because its public rows endpoint returned HTTP 502 and later timed out.

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
