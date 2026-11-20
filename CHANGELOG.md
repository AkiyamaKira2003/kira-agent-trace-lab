# Changelog

## v0.5.0.dev1 — research-only prerelease candidate (not stable v0.5.0)

This is a limited offline research prerelease **candidate**, not
a live-agent security product or independently validated protection
rate. See [dev1 release notes](docs/RELEASE_NOTES_V050_DEV1.md)
and [release gate](docs/RELEASE_GATE_004AI.md).

- ATL-004AH: redact private filesystem path components and raw JSON
  parser exception text in CLI read/import error diagnostics while
  retaining bounded I/O, invalid UTF-8, malformed JSON and nesting
  categories. Five installed importer commands and evaluate/compare
  paths probed using isolated self-authored private-looking markers.
  No claim of general-purpose trace anonymization.
- ATL-004AG: optional compare-policies --output text/JSON report using
  the existing atomic no-clobber writer, explicit --overwrite and
  both-source file protection. Preserves original stdout and exit 0,
  including case-ID pseudonymization, with installed-wheel checks.
- ATL-004AF: add a strictly bounded offline import-responses-sequence
  command for a caller-authored ordered array of completed Responses
  API objects. Reject duplicate response/call IDs, inconsistent explicit
  previous_response_id links, unsupported hosted tools and oversized
  archives without inferring provenance, consent or executing calls.
  Keep the single-response importer unchanged.
- ATL-004AE: opt-in evaluate --summary-only JSON/text for deterministic
  aggregate caller-label counts without individual case, tool or
  argument values; explicit unverified provenance and no real-world
  security-accuracy claim. Preserve default output and mismatch exit 1.
- ATL-004AD: fix destructive evaluate --output report writes; add default
  no-clobber, explicit --overwrite, atomic complete-file publication,
  symlink/input protection and focused fault-injection plus installed CLI
  smoke tests. Keep original evaluation verdict and exit 0/1 semantics.
- ATL-004AC: begin a distinctly versioned post-prerelease development cycle.
  Derive wheel/source-archive filenames from source metadata across QA and CI,
  without rebuilding or replacing the already-published v0.5.0.dev0 release.
  No change to the offline security evaluation contract or user-grant evidence.

## v0.5.0.dev0 — research-only prerelease published 2026-11-21 (not stable v0.5.0)

This version is an explicitly limited research prerelease:
not an AI-agent runtime defense, authorization service, or independently
validated prompt-injection detector. Synthetic fixtures and recorded
policy decisions do not imply verified human approval or protection rates.
See [research release notes](docs/RELEASE_NOTES_V050_DEV0.md) and
[release gate](docs/RELEASE_GATE_004AA.md).

- ATL-004Z: optional compare-policies --redact-case-ids mode with stable per-report aliases, preserving verdicts while omitting original case IDs from text/JSON; explicit limits and installed CLI parity tests.
- ATL-004Y: compare identical offline recorded cases under baseline versus candidate policy-only documents, displaying deterministic allow/deny transitions and reason codes without argument values or invented authorization/accuracy claims. Installed console/module parity and multi-platform CI verified.
- ATL-004X: introduce bounded read-only OpenAI Responses API function_call output import from one completed locally saved response. Preserve order and JSON arguments, reject unsupported hosted/partial calls, never infer approval, and verify installed wheel and source archive with synthetic fixtures.
- ATL-004W: independently smoke-test the installed module and console launcher on all three trace import formats for default no-clobber exit 2, explicit --overwrite, exact on-disk output integrity and no unrelated or temporary file changes.
- ATL-004V: allow only CRLF/LF line-ending equivalence when comparing a verified source archive to a Git checkout; keep content drift, malformed carriage returns and private-path rejection fail-closed.
- ATL-004U: make the source-distribution archive minimal and MIT-only, excluding tests that cannot run without repository fixtures and source-only research material; add fail-closed tar inventory, license, source-bytes, metadata, privacy and installability CI checks with six new tests.
- ATL-004T: add repository/documentation/issue links to wheel project metadata and fail-closed release metadata verification in isolated wheel smoke; record a source-linked v0.5 research release-gate matrix with explicit authorization, representative benchmark and qualified showcase HOLD statuses.
- ATL-004S: make first-time trace-import output publication failure-atomic via same-directory private temporary file and exclusive hardlink; preserve no-clobber semantics and add interrupted-write, link and replace fault-injection tests.
- ATL-004R: prevent silent replacement of pre-existing trace-import output files; require explicit --overwrite for atomic regular-file replacement and reject symlink outputs, with cross-format and hardlink safety regression tests.
- ATL-004Q: reconcile existing OTLP/SWE/AgentDojo importers with ATL-005 without duplicating features or waiving human authorization gates; prevent malformed nested OTLP kvlist values from echoing untrusted property names in error locations.
- ATL-004P: redact untrusted duplicate/unknown JSON property names and tool identifiers from schema validation error messages, while preserving strict rejection and trusted field-location diagnostics; regression tests cover CLI stderr.
- ATL-004O: verify the real pip-installed console launcher from an isolated wheel target on Windows/POSIX, comparing the permissive and task-scoped demo exit codes and JSON with module invocation; negative checks reject absent or divergent entrypoints.
- ATL-004N: self-authored permissive-vs-task-scoped policy CLI contrast, including an intentional mismatch (exit 1), a five-case grant/replay demo, isolated installed-wheel verification and release-preflight limitations; no independently validated permission or safety metrics.
- ATL-004M: optional two-build SOURCE_DATE_EPOCH wheel comparison, negative tests for differing bytes/unsafe inputs, and per-runner CI verification; no cross-platform identity claim.
- Add an offline, bounded single-run AgentDojo recorded tool-call importer and CLI.
- Add synthetic fixtures, negative tests and CI smoke; old schema 1.0/1.1 and existing importers remain compatible.
- Independently import two pinned AgentDojo benchmark runs and compare a permissive allowlist to a simulated-calendar-task allowlist. The selected injected run contains an out-of-scope email action that the permissive allowlist accepts. These are synthetic-scenario contrasts, **not** real-user authorization accuracy metrics.
- Add a complementary pinned AgentDojo user-task counterexample: sending a summary email to the simulated task's designated recipient is within **tool/recipient** scope but rejected by a blanket no-send policy. The benchmark utility flag is false and content correctness/real-user consent are explicitly not established.
- Introduce a predeclared, source-pinned **cross-suite sampling** manifest and bounded audit (banking/workspace × no-injection/injection-attempt): source listing and four SHA-256 verified recorded runs, twelve negative/positive tests and explicit abstentions for all real-user authorization labels. No model safety detection rate is claimed.
- Preregister a broader 24-slot, four-suite/three-condition AgentDojo study in Git before recording new outcomes. Add bounded source audit and source-hash metadata manifest: 20 present, 4 explicitly missing Slack `injection_task_0` records, zero independent reviews, 24 simulated-scope reviews pending and 24 genuine-human-grant abstentions. Do not silently substitute attack IDs or infer human grants from exposures.
- Add ATL-004H privacy-minimized AgentDojo review packet: source-hash verification for four original task-code files, 48 action-name/ordinal entries retaining all 24 planned slots, and fail-closed **provisional-only** dual-review structural checks. No task prompts, arguments, recipients, publisher outcomes, authenticated reviewers or accepted agreement are claimed.
- Add ATL-004I opt-in exact-byte task-source span SHA verification for private review citations, with bounded immutable source downloads, nonoverlap/line limits and negative tests. Verified citation bytes are not evidence of independent human reviewers, semantic authorization or genuine consent.
- Add ATL-004J source-verified metadata-only feasibility matrix for eight AgentDojo user-task definitions, preserving 24 planned/20 present/four missing exposures. Report benchmark reference-tool-name overlap without claiming permission, semantic correctness or detector accuracy; all real-human labels abstain.
- Add ATL-004K bounded optional recorded argument-key/type shape inventory, preserving pinned run hashes, action order and missingness. Redact unrecognized argument names and never publish argument values, real consent or security effectiveness claims.
- Add ATL-004L installed development-wheel QA: build and install wheel without runtime dependency resolution, run synthetic AgentDojo import/evaluation outside source checkout, verify research source scripts and local evidence are excluded from package, and test via Windows/Linux CI matrix. This is reproducibility evidence only.

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
