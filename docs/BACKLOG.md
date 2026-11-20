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
| ATL-009 | NOT_STARTED | Design task-bound authorization policy and negative controls | ATL-004A | Issue #5; written contract distinguishing legitimate forwarding from hijacked forwarding without inferred user consent | 20m |

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
