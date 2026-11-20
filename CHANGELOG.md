# Changelog

## v0.2.0 — feature release candidate (2026-11-20)

- Read-only importer for a limited OTLP/HTTP JSON execute_tool span format.
- Required explicit human label, tool name, captured arguments, trace ID and timestamp.
- Strict refusal to merge multiple traces or silently infer missing tool arguments.
- Additional import tests and CI smoke test.

## v0.1.0 — 2026-11-20

- Deterministic allow/deny policy engine, strict bounded JSON suite, stdlib CLI.
- Synthetic safe and adversarial fixtures, 16 initial unit tests.
- Python wheel build and four-platform-version CI matrix passed.

These releases describe software functionality, not a measured AI model-safety result.
