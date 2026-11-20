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
| ATL-012 | DONE (action-level) | Independently reproduce a pinned external benchmark-run row import | ATL-011 | [Issue #9](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/9); 48 source actions independently reproduced from pinned Parquet; full conversation/patch bytes and human authorization labels are explicitly outside this gate | 25m |
| ATL-012A | DONE | Verify one public recorded benchmark row can be imported without executing tools | ATL-011 | First-rows preview complete; 107,514-byte private row SHA-256 recorded; 48/48 tool calls parsed; no raw trace on GitHub | 20m |
| ATL-012B | DONE | Verify preview cache's reported revision and repeated row-byte consistency, without bulk download | ATL-012A | Hub revision metadata and viewer X-Revision match; saved row SHA-256 matches fresh preview; 69 local tests PASS; not a pinned-Parquet proof | 20m |
| ATL-012C | DONE | Retrieve relevant action columns directly from immutable source shard via bounded HTTP byte ranges | ATL-012B | 14,327,528 transferred bytes, 48 actions and 97 roles exact match; 79 local tests PASS; no full source-row equality/authorization claims | 25m |
| ATL-013 | DONE | Verify and publish correctly scoped stable package v0.4.0 | ATL-012C | [PR #12](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/pull/12), 79 local tests + merged-main CI 4/4 PASS, twice-built wheel hash identical with pinned epoch, isolated installed CLI smoke, released wheel/downloaded hash verified | 25m |
| ATL-004B | DONE (source-classification only) | Verify independently authored scenario labels and abstain on unproven real-user grants | ATL-004/012C | Two pinned AgentDrift source hashes/step labels checked, 1 scenario allow + 1 deny + 2 verified-consent abstentions, reviewed metadata and negative tests; not real-user authorization ground truth | 25m |
| ATL-004C | NOT_STARTED | Independently define a simulated-task boundary from an AgentDojo recorded run | ATL-004B | Pin source and exact rights, legitimate task + attacker objective + recorded actions, and test explicit simulation labels without claiming real consent | 25m |

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

### Live recorded-row format verification checkpoint — 2026-11-20

- Alternate Hugging Face `/first-rows` succeeded for NVIDIA `Open-SWE-Traces/v1.0/sweagent`, first row, zero `truncated_cells`, 97 messages. Hub HEAD observed concurrently: `4fa4c2ae9afc6b397bc50391d43450c79993c138`. Source repo license on row: Apache-2.0; dataset-level CC BY 4.0.
- Raw row saved **only** under gitignored `artifacts/` on KIRA, 107,514 bytes, SHA-256 `5dd6520877d2b0b95e6e3bfa39f868d36a3429c821f7d768b200a6ca8edebb40`. Complete `import-swe` run succeeded: **48 recorded tool calls parsed** (28 bash, 18 str_replace_editor, 2 submit), with no execution; results and structural policy also gitignored.
- **ATL-012A DONE** = verified format interoperability on one externally recorded *benchmark run*. **ATL-012 remains IN_PROGRESS** = cannot prove source row corresponds to an explicitly pinned dataset commit from the preview cache alone. No independent authorization label or population-level security benchmark.
- **NEXT_ACTION:** inspect Hugging Face's official revision-specific dataset access methods and map a pinned dataset commit to the same saved sample SHA-256 without bulk 200 MB+ downloads or publishing raw trace contents. If not feasible, record exact blocker and seek a smaller explicitly licensed revision-pinned recorded trajectory. Keep `v0.4.0.dev0` experimental and do not promote to stable on format smoke alone.

### Fixed-loop closeout / preview release checkpoint — 2026-11-20

- **Published preview:** [v0.4.0.dev0](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.4.0.dev0) marked GitHub **prerelease** (NOT stable), tagged on reviewed commit `6f21ff1cc8afc6f5c91b35ef7ba30776cd0183c6`.
- **Release artifact:** `kira_agent_trace_lab-0.4.0.dev0-py3-none-any.whl` (18,079 bytes); SHA-256 `c20bbf32b3c8c02b688db72463ed4cfcf68bd8e09580e840b3475a4b85490bab`. Installed in an isolated target and smoke-tested with the offline SWE importer, evaluator and schema-1.1 task-grant example.
- **CI evidence:** [main run 44682706126](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/actions/runs/44682706126) **4/4 PASS** (Windows/Linux, Python 3.10 and 3.12). Local suite **63/63 PASS** after sanitized external-row evidence commit.
- **Stable release:** [v0.3.0](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.3.0) unchanged. Neither preview nor stable release claims production tool authorization or reliable attack detection.
- **Remaining:** Issue #9 OPEN; external preview row SHA-256 and contemporaneous dataset HEAD are recorded but not cryptographically linked to a pinned revision. No independently labeled authorization corpus or meaningful safety benchmark; raw data remains local in ignored `artifacts/`.
- **Exact first action next loop:** via KIRAA KPC Core, confirm `main` and working tree, inspect Issue #9 and `docs/RECORDED_TRACE_SOURCE_AUDIT_20261120.md`, then consult official Hugging Face revision-specific access documentation. Determine a reproducible pinned-row retrieval method without downloading giant Parquet shards; compare its SHA-256 against the locally cached row or explicitly document why equivalence remains unverified.

### ATL-012B checkpoint — 2026-11-20 (server-attested preview)

- **Implemented:** optional bounded network audit `scripts/audit_hf_preview_revision.py` plus six negative/positive tests. The shipped evaluator and importer stay offline. Preview metadata `X-Revision`, Hub pinned metadata `sha`, untruncated first row and locally cached canonical JSON digest all agree; 107,514 bytes, SHA-256 `5dd6520877d2b0b95e6e3bfa39f868d36a3429c821f7d768b200a6ca8edebb40`, license CC BY 4.0 / row source Apache-2.0.
- **Local proof:** `python -m unittest discover -s tests -q` **69/69 PASS**; `python -m compileall -q agent_trace_lab scripts tests` PASS; audit command returned `SERVER_ATTESTED_PREVIEW_MATCH`, `trace_executed=false` and `source_parquet_row_independently_verified=false`.
- **Still open:** `ATL-012` / Issue #9 needs *independent* pinned-shard row proof or documented inability to obtain it. Do not equate the viewer's claim with a cryptographic guarantee or human authorization ground truth. Do not promote experimental v0.4 or alter KiraShop yet.
- **NEXT_ACTION:** review and merge ATL-012B after PR CI, re-run tests on merged `main`, then investigate a read-only ranged-Parquet first-row extraction from the fixed Hub commit with a strict transfer budget; if unsupported, publish the exact blocker in Issue #9 and move to an appropriately scoped alternative recorded source. No large download without a size gate.

### ATL-012C checkpoint — 2026-11-20 / immutable source action replay

- **Source:** NVIDIA `Open-SWE-Traces`, commit `4fa4c2ae9afc6b397bc50391d43450c79993c138`, shard `data/sweagent/minimax_m25/swe-rebench-v2/train-00000-of-00019.parquet`, metadata 2,500 rows in one row group, shard size 208,152,116 bytes.
- **Independent verification:** read only importer-relevant columns via HTTP 206 with a 20 MiB cap. Pinned source row #0 identity/roles and exact normalized 48-action sequence match the private preview; action JSON hash `27bf568b78716733ca776a0fc558f7fd2addfe5c77ee6fd46f13f9cbc36b13cc`. **14,327,528 bytes / 10 range requests**, not the whole 208 MB shard; no tool execution. Sample source repo Apache-2.0, dataset CC BY 4.0.
- **Tests:** `python -m unittest discover -s tests -q` **79/79 PASS**; real end-to-end pinned partial-column probe PASS. Optional PyArrow 21 installed only in ignored `artifacts/rowproof_deps`; no runtime package dependency change. Raw recorded arguments never staged.
- **Scope:** action-field provenance is independently tied to immutable Parquet revision; complete row/content byte identity is NOT proven, and no independent human authorization ground truth exists. The tool remains an offline audit prototype.
- **NEXT_ACTION:** PR and GitHub CI review, merge into `main` and check Issue #9 action-level closure; then ATL-013 inspect README / wheel build / offline CLI / GitHub release gate. ATL-004 independent labels remain open; do not claim safety detection accuracy or integrate KiraShop prematurely.

### ATL-012C merged checkpoint / ATL-013 release-readiness — 2026-11-20

- **Verified main:** PR [#11](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/pull/11) merged at `539e548f35d741c307956d1ffd3fae6edea07ea7`, 8/8 Windows/Ubuntu CI jobs PASS and 79/79 local tests PASS on merged `main`; clean working tree. [Issue #9](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/9) CLOSED for pinned-source action-level interoperability only; broader ATL-004/006 human authorization label validation remains unfinished.
- **Release review:** pre-existing package `v0.4.0.dev0` wheel successfully rebuilt offline in ignored `artifacts/release-audit/`; CHANGELOG was stale and erroneously still described upstream 502 as current incompatibility. A version/documentation release candidate is being checked separately as `release/v0.4.0`.
- **NEXT_ACTION:** build candidate `0.4.0` wheel, isolate-install and smoke-test all CLI flows from outside the source checkout; check wheel content, docs, privacy and Git diff. Merge only with passing Windows/Linux PR CI. If all gates pass, publish an accurately scoped v0.4.0 GitHub release and verify the published wheel. **Do not** label the research prototype a security enforcement product or claim task-authorization detection accuracy.

### Verified publication / final release checkpoint — 2026-11-20

- **Machine / ownership:** KIRAA via KPC Core, project `C:\Projects\kira-agent-trace-lab`. No pre-existing project state or KPCenter registration, and neither was created. The only working repository is the existing GitHub project.
- **Released:** [v0.4.0](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.4.0), non-prerelease GitHub release, on annotated `v0.4.0` tag pointing to **merged-main commit** `6e115da5e7a56c84bc9865ac0d3a065ef62d68c0`; [PR #12](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/pull/12) MERGED.
- **CI:** [merged main run 44723818506](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/actions/runs/44723818506) **4/4 PASS**, Windows and Ubuntu with Python 3.10/3.12. Local source `python -m unittest discover -s tests -q` **79/79 PASS**. `compileall` PASS. Wheel isolated-install tests run **outside source checkout** for baseline 8/8, task grants 9/9, SWE import/eval and OTLP import/eval.
- **Artifact:** `kira_agent_trace_lab-0.4.0-py3-none-any.whl`, **19,061 bytes**, SHA-256 `112d980365dba670dee2494f5bd5ecf09204a3ee0168906fe95b7e0d1d7d9fde`. Two independent local builds using `SOURCE_DATE_EPOCH=1795172363` produced identical hashes; the **published** wheel was downloaded again from GitHub and independently hashed to the same value as the locally built wheel and published `SHA256SUMS.txt`. Wheel archive contains package, LICENSE and standard metadata only; no raw traces, secrets, project-specific artifacts or optional PyArrow dependency.
- **Ground-truth boundary:** independent pinned-source Parquet action-field interoperability verified in ATL-012C; **not** entire conversation content equality or independent human task-approval labels. Release is a stable distribution of an offline research prototype with clearly labeled experimental SWE importer. No real-world authorization accuracy, prompt-injection defense or runtime enforcement claim. [Issue #9](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/9) CLOSED with these limits.
- **Current project:** still active, because **ATL-004** is IN_PROGRESS and **ATL-006** independent external authorization evaluation and **ATL-007** qualified portfolio showcase remain unfinished. Do not mark project COMPLETE or create a competing repo yet.
- **NEXT_ACTION:** **ATL-004B (20–25-minute scoped task)** — research an independently justified labeling methodology for two or more third-party recorded action traces with source URL, license, task/grant authority provenance, review rubric and an explicit unknown/abstain outcome where permission cannot be authenticated. Do not infer authorization labels from issue `resolved` or a passing test. Keep source conversations outside Git until privacy/license review; verify all 79 tests still PASS if any code or fixtures change. Then decide whether an independently labeled corpus can support honest evaluation metrics (ATL-006) or whether to report an irreducible evidence gap.

### ATL-004B evidence-classification checkpoint — 2026-11-20

- **Machine/Core:** KIRAA using KPC Core; existing repository C:\Projects\kira-agent-trace-lab. Neither KPC project state nor KPCenter registration exists; no initialization was performed.
- **Sources:** AgentDrift at pinned Git revision 014a514fa998b4ac4519579fceb8a5884b379bda; author-provided synthetic step labels and CC BY 4.0 dataset rights reviewed. The two source records' exact byte hashes, IDs and step-label counts were rechecked with bounded direct upstream requests. No raw conversations or tool argument values were committed.
- **Implemented:** docs/authorization_label_review.json, docs/INDEPENDENT_AUTHORIZATION_LABELING.md, scripts/verify_label_review.py and tests/test_label_review.py; README links to the provenance/abstention rubric. The author-labeled scenarios provide one allow and one deny, while BOTH human-authorization verdicts are abstain (0 verified real-user grants).
- **Verification:** 88/88 local unit tests PASS, compileall PASS. Offline manifest audit PASS; opt-in pinned-source retrieval PASS (2/2 exact records). The validator explicitly fails any attempt to turn this synthetic dataset into authenticated-consent benchmark metrics. Original schema and evaluator were not changed.
- **Remaining research:** ATL-004 and ATL-006 are still OPEN: no independent authenticated user approval logs. Do not report authorization detection accuracy from synthetic author labels or NVIDIA task success. README and stable v0.4.0 remain accurate; no KiraShop integration yet.
- **NEXT_ACTION:** ATL-004C (estimated 20-25 min) — pin a legitimate task and attack objective from an AgentDojo recorded run, check source rights, and produce an explicitly SIMULATED task-boundary evidence fixture with rejection/abstention controls. Do not claim this proves genuine human consent; if raw recorded runs or rights cannot be validated, document the exact blocker and choose a smaller source.
