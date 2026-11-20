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
