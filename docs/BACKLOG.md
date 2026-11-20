# Tasks and continuation checkpoint

Machine **KIRAA** | Core **KPC Core** | Local root **C:\Projects\kira-agent-trace-lab**

No pre-existing KPC project state or KPCenter registration: intentionally **no new KPC state / Master Plan**. This is a lightweight, repository-local task record; use actual source, Git and tests to verify before resuming.

Each task is scoped to an **estimated** 10–25 minutes; there is no actual elapsed-time measurement.

| ID | Status | Objective and scope | Dependency | Acceptance / test | Est. |
| --- | --- | --- | --- | --- | --- |
| ATL-001 | DONE | Strict policy schema and static trace evaluator | None | Validation, deterministic verdicts, unittest PASS | 25m |
| ATL-002 | DONE | CLI, JSON/text reports, safe sample suite | ATL-001 | Sample 8/8 labeled fixtures, exit behavior tested | 20m |
| ATL-003 | DONE | README, research, CI, security and packaging checks | ATL-001/002 | 16 tests + wheel PASS; GitHub Actions 4/4 PASS on commit 43507d1 | 25m |
| ATL-004 | IN_PROGRESS | Independent labeling/evaluation beyond our own synthetic fixtures | ATL-003 | External synthetic subtask complete (ATL-004A), but authentic traces and representative labels still absent | 25m |
| ATL-005 | NOT_STARTED | Read-only adapter for one real agent trace schema | ATL-004 | Correct import without executing any tool actions | 25m |
| ATL-006 | NOT_STARTED | Evaluation against externally labeled dataset | ATL-005 | Reproducible precision/recall with failure cases | 25m |
| ATL-007 | NOT_STARTED | Qualified portfolio showcase | ATL-006 | Actual demonstration and evidence, no KiraShop regression | 20m |
| ATL-008 | DONE | Import read-only OpenTelemetry execute_tool spans | ATL-003 | #1 closed by merged PR #2; single-trace parsing, missing-argument rejection; 29 unit tests and PR CI 4/4 PASS | 25m |
| ATL-004A | DONE | Attribute external AgentDrift *synthetic* examples, expose semantic policy gap | ATL-003 | PR #4 merged, issue #3 closed; 31 tests, GitHub CI 4/4 PASS | 25m |
| ATL-009 | DONE | Opt-in schema 1.1 with deterministic task-bound grants and negative controls | ATL-004A | Issue #5 CLOSED by merged PR #6; 50 local tests PASS; GitHub CI 4/4 PASS; v0.3.0 release | 20m |
| ATL-010 | DONE | Audit real benchmark-run trajectory sources, schema and reuse limits | ATL-004A | Pinned NVIDIA/Nebius revisions, licenses, 1 sampled NVIDIA row structure; see source audit | 20m |
| ATL-011 | DONE | Experimental offline importer for one SWE-style recorded tool-call row | ATL-010 | [Issue #7](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/7) CLOSED by PR #8, 63 local tests PASS, PR CI 4/4 PASS; independent real-row validation is a separate gate | 25m |
| ATL-012 | BLOCKED | Validate imported trace against pinned external benchmark-run row | ATL-011 | [Issue #9](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/9); published dataset endpoint HTTP 502/timeout; secure data retrieval and licensing needed | 25m |

Local baseline **2026-11-20**: Python 3.12.10, **11 unit tests passed**, **8/8 example labels matched**; no claim of real-agent benchmark performance.

## Verified release checkpoint — 2026-11-20

- Active project: `C:\Projects\kira-agent-trace-lab` (KIRAA / KPC Core); remote `AkiyamaKira2003/kira-agent-trace-lab`.
- Branch: `main`; verified merge commit `a760eac2274a25d2be5d566320c426098c4af6ad` (pull request #2).
- Checked: `python -m unittest discover -s tests -q` **29/29 PASS** on merged `main`; package wheel `0.2.0` built on KIRAA.
- GitHub CI: pull-request run 44676997845, **4/4 PASS** on Ubuntu/Windows, Python 3.10/3.12, commit `965562a` preceding merge. Check main's own CI separately for subsequent documentation changes.
- Complete: ATL-001, ATL-002, ATL-003, ATL-008. No real-agent benchmark has been run, so efficacy remains unknown.
- Open risk: synthetic examples and synthetic OTLP export; no independent real-world labels, no runtime enforcement, no claim of agent attack protection.

**NEXT_ACTION: ATL-004 — seek permissively licensed, authentic tool-use trace examples and independently justified allow/deny labels, with source URLs, licenses, timestamp and analyst notes.** Acceptance: documented provenance and at least one externally grounded benign/unsafe counterexample without unverified performance claims; tests must retain 29/29 baseline and labels must not be inferred from this evaluator's verdicts.

### Completed issue #3 — merged counterexample (2026-11-20)

AgentDrift is a **third-party synthetic dataset**, not authentic production telemetry. The isolated two-record adaptation shows one correctly allowed benign trace and one expected unauthorized trace allowed by a deliberately permissive tool-name policy. PR #4 merged to `main` at commit `3cf052ad2c77f804cf945c4e41ac674c73a76cf1`, with GitHub Actions run `44678337210` 4/4 PASS. Re-running tests on merged KIRAA source: **31/31 PASS**; GitHub issue #3 CLOSED. This completes the *narrow external counterexample* subtask ATL-004A; the broader external/real-world evaluation task ATL-004 is still IN_PROGRESS.

Released version **v0.2.0** remains available at `https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.2.0` with verified Python wheel (SHA256 `dd2382604b68c609be4bdd0edf84cf3239ecb0bc4638b0bebfd24f6062ed4e1a`). The post-release case-study commit is on `main` but is not part of the tagged v0.2.0 wheel.

**NEXT_ACTION:** [Issue #5](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/5), ATL-009 task 1 — design explicit **user-task authorization inputs**, including a legitimate email-forward case, an unauthorized forwarding case, and deny-by-default behavior when user-grant evidence is missing. Use Cedar and OPA's documented authorization concepts as references, not as dependencies. Do not let an LLM guess permissions; require externally supplied authorization facts. Then implement in a separate small task and verify compatibility against the 31-test baseline. Continue hunting for consented authentic tool traces; do not call the two AgentDrift samples a statistically representative benchmark.

### Fixed-loop checkpoint — 2026-11-20 / ATL-009

- Verified machine KIRAA and KPC Core; existing repository, no KPCenter state and no KPCenter registration; do **not** initialize governance.
- Starting baseline: clean `main` at `930c1be99e10f196e2ea15916a1446bd18ff804b`, GitHub CI success, 31/31 tests pass.
- Current feature branch: `feat/task-bound-authorization`, new docs/TASK_AUTHORIZATION_DESIGN.md.
- ATL-009a design complete: compare blanket blocking, model-inferred authorization, full Cedar/OPA integration and narrow exact-action grants. Chose grant matching plus explicit external trust boundary.
- ATL-009b local implementation: 1.1 schema + optional case grants, deny on missing grant, exact JSON matching, unique grant IDs, single-use consumption, no grant override for other restrictions, legacy 1.0 preserved; 49/49 unit tests PASS, 9/9 synthetic grant fixture labels match.
- **Important limitation:** source_ref is an unauthenticated reference. This evaluator cannot prove user approval, and does not authenticate caller, origin, temporal validity, or task identity. No real-agent benchmark claims.
- **NEXT_ACTION:** finish package/CLI smoke, Git diff and credential scan, push branch and open PR; verify GitHub Actions Windows/Linux before merging. Then re-run merged-main tests and issue a v0.3.0 release only if package and CI pass. Continue ATL-004 real-world research independently after shipping.

### Verified release checkpoint — v0.3.0 / 2026-11-20

- KIRAA / KPC Core; project root `C:\Projects\kira-agent-trace-lab`, no KPC state / registration (no governance initialization).
- ATL-009 design `6410232` and implementation `ec233bc` merged through [PR #6](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/pull/6); [issue #5](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/5) CLOSED.
- Verified merge commit `4e116c9354b38de32a754245091922c3087f7779`; `main` clean immediately after merge.
- Local Python 3.12 tests 50/50 PASS; task grant synthetic fixtures 9/9 labels match; schema 1.0 regression and OTLP import work.
- GitHub Actions [PR run 44679938471](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/actions/runs/44679938471) 4/4 PASS on Windows/Ubuntu and Python 3.10/3.12. Merged-main run `44680110966` successful.
- Official [v0.3.0 release](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.3.0), wheel built from merged `main`, installed in isolated target and CLI smoke-tested; SHA-256 `aa58c36f26518b008684590296468460717fa8a3bb27a698ebe6f39f88f5f955`.
- **Critical limit:** no cryptographic verification or trustworthy issuance of `source_ref` grants, no live authorization enforcement. Only self-authored task-grant tests and third-party synthetic AgentDrift cases; no statistically representative agent-safety benchmark.
- **NEXT_ACTION (ATL-004):** find a public, explicitly licensed dataset of **recorded tool executions from real benchmark runs** (not merely generated synthetic narratives). Record pinned source commit, source license and reuse conditions, event format, and which author-provided labels—if any—match this evaluator's policy semantics. Only then implement a small offline adapter or independent QA fixture. Do not make KiraShop changes until evidence supports a useful showcase.

### External recorded-trajectory source audit — 2026-11-20

- [Audit source/reuse/format](RECORDED_TRACE_SOURCE_AUDIT_20261120.md) confirms NVIDIA Open-SWE-Traces CC BY 4.0, pinned Hugging Face HEAD `4fa4c2ae9afc6b397bc50391d43450c79993c138`; inspected one benchmark-run row with 97 messages and 48 tool calls. Raw model actions are **not committed**.
- Source `resolved` field measures task completion, not unauthorized action; no independent task-authorization labels have been established. ATL-004 therefore remains **IN_PROGRESS**.
- A deeper upstream argument check encountered HTTP 502; this does **not** count as validated event parsing. Another candidate, Nebius SWE-agent-trajectories, has extra model-output/repository-license considerations.
- **NEXT_ACTION:** ATL-011, [Issue #7](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/7) — implement read-only import of user-supplied single JSON row; strict bounds and schema validation; negative tests; deterministic normalizer. Test against a synthetic format fixture before trying a pinned, licensed external row. Never execute tools or infer authorization from task resolution.

### Experimental importer checkpoint — 2026-11-20

- Branch `feat/swe-recorded-trace-import` based on research commit `6379236390c507c75fa8c30402e8a892bab886e4`.
- Local implementation `agent_trace_lab/swe.py` imports assistant function calls from a single JSON row; generic argument parser reused with OTLP; CLI `import-swe` requires an externally supplied label. No network or action execution.
- Self-authored structural fixture and 13 new negative/positive unit tests; entire test suite **63/63 PASS**; synthetic CLI import and evaluation PASS.
- Upstream NVIDIA sample envelope checked (48 calls), but HTTP 502 and subsequent timeout prevented external raw-data end-to-end validation. **EXTERNAL_E2E = NOT_VERIFIED**.
- **NEXT_ACTION:** complete source/CLI QA, packaging, secret scan and CI for experimental implementation; document this caveat in PR. Merge only after synthetic/compatibility checks are green; keep true external-compatibility task separate and do **not** tag a production release based only on synthetic tests.

### Fixed-loop handoff checkpoint — 2026-11-20 / ATL-011

- **Project / machine:** Kira Agent Trace Lab, KIRAA via KPC Core, path `C:\Projects\kira-agent-trace-lab`. No pre-existing KPCenter project state/registration, and none created.
- **Merged implementation:** [PR #8](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/pull/8) MERGED; issue #7 CLOSED. Merge commit `a5e574800b7309fe7cbe1b73d97ba22e9aa28285`, local `main` fast-forwarded to match origin/main.
- **QA evidence:** Python 3.12 `python -m unittest discover -s tests -q` **63/63 PASS on merged main**; `import-swe` synthetic CLI import and `evaluate` PASS; v0.4.0.dev0 wheel built and isolated-install smoke-tested before merge. PR [GitHub Actions run 44681796714](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/actions/runs/44681796714) **4/4 PASS** on Windows/Linux, Python 3.10/3.12.
- **Security/legal:** no raw NVIDIA dataset or model conversations committed, test fixture self-authored. Staged diff and common credential patterns checked prior to PR. Permission labels and source_ref are not authenticated by this tool.
- **Release:** last officially tagged stable release [v0.3.0](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.3.0). Experimental `0.4.0.dev0` lives on main but **no v0.4 stable release**; external compatibility remains not verified.
- **Outstanding blocker:** upstream NVIDIA dataset rows API has returned HTTP 502 and timeout in multiple attempts, so **external raw-row E2E NOT_VERIFIED**. No benchmark safety score or task authorization ground truth established; ATL-004 remains IN_PROGRESS.
- **NEXT_ACTION:** [Issue #9 / ATL-012](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/9), obtain one row at pinned revision via an alternative publisher-supported route (not repeatedly retrying failing endpoint). Confirm row-level source code license; keep raw data inside gitignored `artifacts/`. Test `import-swe` on it without executing tools, record sanitized action counts and failure details. If still blocked, preserve NOT_VERIFIED and research smaller license-clear benchmark trace.
