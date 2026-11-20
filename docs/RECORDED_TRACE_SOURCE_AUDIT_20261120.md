# ATL-010 — audit of recorded benchmark-agent trace sources

**Audited:** 2026-11-20 (Asia/Ho_Chi_Minh). **Scope:** public dataset provenance, licensing, tool-call format and suitability for an offline agent-action evaluation. This document does not republish any raw model conversations, source files or code patches.

## Findings and candidate selection

### 1. NVIDIA Open-SWE-Traces — prioritize for structural interoperability

- Publisher: NVIDIA, dataset [nvidia/Open-SWE-Traces](https://huggingface.co/datasets/nvidia/Open-SWE-Traces), [dataset card](https://huggingface.co/datasets/nvidia/Open-SWE-Traces/blob/main/README.md).
- HEAD observed through the Hugging Face dataset API: `4fa4c2ae9afc6b397bc50391d43450c79993c138`.
- Dataset-level license reported by publisher and API: **CC BY 4.0**. Each source-repository record also has a separate `license` field; downstream users must respect applicable original-code rights.
- Version examined: config `v1.0`, split `sweagent`, row offset 0 of [the dataset-server rows endpoint](https://datasets-server.huggingface.co/rows?dataset=nvidia/Open-SWE-Traces&config=v1.0&split=sweagent&offset=0&length=1).
- Verified a returned row from a live request: 97 recorded messages; roles `system`, `user`, `assistant`, `tool`; 48 tool calls with function names `bash` (28), `str_replace_editor` (18), `submit` (2).
- The first tool-call envelope contains keys `type`, `id`, `function`, with `function.name` and `function.arguments`. Arguments were observed as **strings**, not already-decoded objects. The sampled source-repository license field was `Apache-2.0`.
- Public schema has `instance_id`, `repo`, `license`, `language`, `trajectory_id`, `messages`, `tools`, `resolved`, `metadata` and `hf_dataset_name`.
- **Meaning of labels:** `resolved` indicates benchmark task/issue resolution, **not whether a tool action was authorized**. The dataset is classified by its publisher as hybrid automated/synthetic; the *executions* are collected in benchmark harnesses, not in a consenting production-user environment.
- **Remaining limitation:** one subsequent attempt to fully decode and validate all tool-call arguments returned upstream HTTP **502**. This is an unverified step, not evidence of valid or invalid JSON for all 48 calls. The dataset-server response is not guaranteed to be pinned to the HEAD hash; retain the observed revision in provenance and use a pinned dataset revision for any future reproducible extraction.
- **Follow-up attempted:** a further request for that first complete public row **timed out** before any local copy could be written. Therefore, no real raw-data fixture has been persisted or tested against the current importer. This external validation gate remains **BLOCKED/NOT_VERIFIED**; do not count synthetic parser tests as a replacement.

#### Subsequent observed live-row interoperability pass (2026-11-20)

- **Alternate publisher API:** [Hugging Face first-rows endpoint, v1.0/sweagent](https://datasets-server.huggingface.co/first-rows?dataset=nvidia/Open-SWE-Traces&config=v1.0&split=sweagent), rather than retrying the previously failing `/rows` endpoint.
- A complete JSON response of 10 preview rows was retrieved; the first row reported `truncated_cells=[]`, i.e. **no preview truncation flagged**. The separately fetched Hub metadata still reported repository HEAD `4fa4c2ae9afc6b397bc50391d43450c79993c138` at retrieval.
- The extracted first-row JSON had **107,514 bytes**, SHA-256 `5dd6520877d2b0b95e6e3bfa39f868d36a3429c821f7d768b200a6ca8edebb40`. The row's source-repository license field is `Apache-2.0`. Full raw content was stored **only** under Git-ignored `artifacts/open_swe_v1_sweagent_firstrow_private.json` on KIRA.
- `python -m agent_trace_lab import-swe` succeeded on that local **recorded benchmark row**. An independently constructed **structural-only** policy allowing the three observed tool names with a 100-action budget produced 48 events: `bash` 28; `str_replace_editor` 18; `submit` 2. The validated local result and policy are also gitignored.
- **External data format E2E = PASS on this one observed row**. This is **not** a supervised authorization test: the explicit `allow` label was caller-supplied for the demonstrative structural allowlist and was not provided by the dataset; its `resolved` task-success field was ignored. The checker did not execute shell commands or model actions.
- **Revision-pinning caveat remains:** the dataset-server preview endpoint is a cache of the publisher's current processed data; retrieving the Hub HEAD SHA at the same time does **not** cryptographically prove the returned preview corresponds to a pinned commit. The recorded local SHA-256 provides byte-level reproducibility of the saved sample, but independently fetching that exact row from a pinned revision remains a separate verification gate under [Issue #9](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/9). Do not mislabel this result as proven pinned-source replay.

#### Reproducible viewer-revision attestation (ATL-012B; 2026-11-20)

- The official [Dataset Viewer API documentation](https://huggingface.co/docs/dataset-viewer/quick_start) describes `/first-rows` as a preview endpoint; the [server architecture documentation](https://huggingface.co/docs/dataset-viewer/server) confirms its response is served from a processed cache rather than on-demand decoding of an arbitrary pinned Git revision.
- Directly fetched [Hub revision metadata](https://huggingface.co/api/datasets/nvidia/Open-SWE-Traces/revision/4fa4c2ae9afc6b397bc50391d43450c79993c138) reports `sha=4fa4c2ae9afc6b397bc50391d43450c79993c138` and dataset-level `cc-by-4.0`. A new, direct request to the publisher's [`/first-rows` endpoint](https://datasets-server.huggingface.co/first-rows?dataset=nvidia/Open-SWE-Traces&config=v1.0&split=sweagent) returned HTTP 200 and **`X-Revision: 4fa4c2ae9afc6b397bc50391d43450c79993c138`**. This is a server-attested dataset revision (not just a separately observed HEAD).
- First row: `row_idx=0`, `truncated_cells=[]`; canonical JSON 107,514 bytes, SHA-256 `5dd6520877d2b0b95e6e3bfa39f868d36a3429c821f7d768b200a6ca8edebb40`, **byte-for-byte equal** to the Git-ignored saved row. Its source-repository license field is `Apache-2.0`. Raw tool arguments were not printed or committed.
- Added reproducible, opt-in `scripts/audit_hf_preview_revision.py`, which checks Hub metadata, the `X-Revision` header, missing/truncated/reordered preview content, exact canonical row bytes and an independently supplied expected digest. Tests reject missing/wrong revision, truncation, row mismatch and license/commit mismatches. Local suite **69/69 PASS** at this checkpoint.
- **Evidence level:** `SERVER_ATTESTED_PREVIEW_MATCH`, not independently reproduced pinned source bytes. The revision-specific underlying Parquet shards are large: first `minimax_m25/swe-rebench-v2` shard **208,152,116 bytes**, first `qwen35_122b/swe-rebench-v2` shard **234,451,253 bytes**. No bulk downloads were performed, and no direct content-hash-to-shard proof was made. Preview cache correctness is still an upstream trust assumption. Issue #9 / ATL-012 remains **OPEN/IN_PROGRESS** for an independent pinned-content replay (or an explicit evidence downgrade) before stable v0.4 release.

#### Independent revision-pinned Parquet action verification (ATL-012C; 2026-11-20)

- **Actual immutable source:** `https://huggingface.co/datasets/nvidia/Open-SWE-Traces/resolve/4fa4c2ae9afc6b397bc50391d43450c79993c138/data/sweagent/minimax_m25/swe-rebench-v2/train-00000-of-00019.parquet`. The publisher Hub revision API confirmed the exact Git commit and dataset CC BY 4.0 license. The row's own source-repository license is `Apache-2.0`. The first Parquet shard size is **208,152,116 bytes**, with one row group containing 2,500 rows.
- **Method:** `scripts/audit_hf_pinned_parquet_actions.py` reads directly from this fixed revision using HTTP **206 Partial Content**, verifies `Content-Range` against the expected shard size, and imposes a **20 MiB absolute transfer ceiling**. An explicitly optional PyArrow 21 reader retrieves only the identity fields, message roles and tool-call name/type/arguments columns. It never downloads prompts, message text, reasoning or patch text. See the README for an isolated install/run command; no new mandatory dependencies are added to the evaluator.
- **Reproduction:** only **14,327,528 bytes** across **10** exact byte-range requests were transferred. First-row `instance_id`, source repo, license, trajectory ID and dataset name match the local cached preview; all **97 message roles** match. The importer independently normalized **48/48 source actions**, with exact ordered tool names and argument objects equal to the preview: `bash=28`, `str_replace_editor=18`, `submit=2`; SHA-256 of canonical normalized action JSON `27bf568b78716733ca776a0fc558f7fd2addfe5c77ee6fd46f13f9cbc36b13cc`. No actions were executed. Local Python unit suite **79/79 PASS**, including bounded range and mismatch cases.
- **Scope of proof:** `PINNED_PARQUET_ACTION_EQUIVALENCE_VERIFIED` means that the exact **fields used by the offline SWE importer** were reproduced from source Parquet at the pinned Git commit. **It does not** prove equality of all original conversation/patch/reasoning bytes, create trusted human authorization labels, or measure attack-detection accuracy. This satisfies the **recorded-action interoperability** gate of Issue #9 / ATL-012, but **ATL-004/006 external authorization evaluation remains unsolved**. No raw conversation rows or arguments were published.

**Recommendation:** a small, strict, **offline-only** importer of a user-provided **single exported row** could turn the recorded assistant tool calls into this evaluator's normal suite schema, skipping tool outputs/system prompts. Do not execute those calls. Require user-provided expected labels; never infer authorization from `resolved`, model explanations or whether the patch passed tests.

### 2. Nebius SWE-agent-trajectories — alternative with extra license review

- Publisher: [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories), card reports 80,036 recorded trajectories and a trajectory field containing reasoning/actions/observations.
- HEAD observed from Hugging Face API: `68195a1450865274106246d0d0296a1d6807b88e`; dataset card/API indicates **CC BY 4.0**.
- Publisher explicitly warns that each original source-repository license applies and that some model outputs have additional **Llama 3.1** usage terms.
- The dataset's target/issue-resolved label is **task success**, not task authorization. Large size (~1.11 GB reported in dataset card) and mixed rights favor examining only specific licensed, redacted examples.

### 3. SWE-bench experiment submissions — inspect rights per submitter

- [SWE-bench/experiments](https://github.com/SWE-bench/experiments) indexes public submissions, their evaluation results and locations of execution logs/trajectories.
- GitHub repository API did **not** supply a recognized license SPDX identifier for this index. More importantly, actual trajectory artifacts are controlled by each submitter in separate repositories or legacy storage. Do **not** assume a unified reuse license.
- Recorded `resolved`/test-pass outcomes cannot establish whether individual tool calls complied with the request's permission boundary.

## Engineering decision for the next small task

**ATL-011 — read-only row importer, proposed (20–25 minutes):**

1. Require one **locally supplied, bounded JSON row**, no automatic network access; reject missing/malformed `messages`, tool-call function name or non-object JSON arguments rather than fabricate an action.
2. Extract only assistant `tool_calls` in original order; never replay shell/editor/submit actions. Skip model reasoning, observations and secret-bearing bodies in the output.
3. Respect existing suite-size/tool-name limits and the externally authored allowlist policy. Reuse JSON schema 1.0/1.1 behavior, with zero inferred task grants.
4. Require a caller-provided `--expected` label for compatibility, but explain that it is **not authenticated ground truth**. Reuse the current `artifacts/` ignore boundary for sensitive local outputs.
5. Test with a **self-authored structural fixture**, then validate against a pinned, license-reviewed public row if the upstream service permits. Do not copy raw model arguments or source-code snippets into the public repository.

**Acceptance:** conversion deterministic; malformed arguments fail closed; legacy CLI/tests remain green; provenance and privacy warnings documented; actual external row validation and any independent authorization label remain distinct gates. If upstream data cannot be inspected reliably, report the validation as **BLOCKED** instead of declaring an external benchmark.

## Explicit non-claims

No real user granted these benchmark agents task permissions to be evaluated by this repository. Nothing here measures detection rate, prompt-injection resistance, security enforcement, general model quality or real deployment behavior. Only recorded *structure and source provenance* were audited.
