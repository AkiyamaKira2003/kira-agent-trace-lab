# ATL-004G — preregistered stratified AgentDojo exposure audit

## Preregistration before retrieval

The frozen [selection specification](agentdojo_stratified_preregistration.json) is committed **before** examining any new recorded-run outcomes, tool sequences or intervention results in this task. It references the MIT-licensed [AgentDojo repository](https://github.com/ethz-spylab/agentdojo) at source Git SHA `089ed468cf3ed0322acc66b0211f26d9d90dbf60`. Its independent **Git preregistration commit** must remain available in history. A later manifest must reference that commit to demonstrate selection was not changed after inspecting outcomes.

**Sampling design:** take all four benchmark suites (`banking`, `slack`, `travel`, `workspace`), task indices **0 and 1** in each suite and three fixed exposure conditions in order: `none/none.json`, `direct/injection_task_0.json`, and `important_instructions/injection_task_0.json`. This is **24 planned source slots**: 4 suites × 2 tasks × 3 conditions. No task or strategy is replaced based on source availability, utility, publisher security flags, recorded tool sequence, or policy outcome. Missing, malformed, and oversize paths remain in the denominator, explicitly reported.

**Budgets:** at most 24 pinned raw file read requests, 64 KiB each and 1.5 MiB total response body; offline metadata manifest max 32 KiB. Inspect source only after preregistration is committed. No benchmark actions, email, banking tool, injected instructions, or AI agents are executed.

**Limitations:** Non-random early-task selection, exactly one attack ID per condition, one recorded model, one fixed upstream revision. Not a population estimate. Exposure is **not** authorization. Absent original human-grant provenance, every real-human authorization label is **abstain**. Publisher utility/security flags are descriptions of harness outcomes, not human consent. The audit will not compute precision/recall/FPR or attack detection accuracy.

## Independent simulated-scope review protocol (not yet conducted)

Task-grant judgments require **independent original task wording and authorized tools/recipients**: recorded calls alone, benchmark attack-success fields, model replies, or publisher utility flags cannot supply authorization ground truth.

1. Form a privacy/rights-reviewed review packet for each sampled `suite/user_task_i`, comprising its pinned task source and minimally redacted tool/recipient **scope**. Source code, attacker instructions, and recorded arguments are untrusted data; do not execute them. Record all omitted/redacted fields and independent task source SHA.
2. Two distinct **actual** reviewers (`reviewer_A`, `reviewer_B`) separately assign `within_scope`, `out_of_scope` or `abstain`, a supporting task quotation/source span, source hash, action ordinal and rationale, blinded to the publisher `utility`, `security`, and each other's label. Do not fabricate reviewer identities, two-model agreement, or evidence.
3. After both reviews, quantify per-action and per-task **coverage / abstention / agreement** with a declared denominator, and keep disagreements as `disputed` pending a third independent adjudicator. If consent provenance or action-target meaning remains unclear, keep `abstain`; do not force a balanced classification.
4. A hypothetical simulation boundary may be evaluated **only** against accepted independently reviewed simulated labels. Human grant status remains `abstain` until authenticated user authorization exists. Label-provenance and agreement must accompany any metrics.

**Review state at preregistration:** no new independent reviews performed, 24 slots planned, zero independently labeled authorizations. The post-retrieval audit must include exact provenance, missingness, tool-call counts and a transparent next-step review gate before treating this as completed evidence.

## Post-preregistration results — 2026-11-21

**Preregistration commit:** `3385f7db5227400cc14caa995b0a9054b3a995f7`. Git confirms the committed specification blob matches the current specification. Only after committing this rule were the 24 fixed paths fetched. The machine-readable, metadata-only [exposure manifest](agentdojo_stratified_exposures.json) records the full 24-row denominator, fixed source paths, source SHA-256 and observed **tool names only** for available files. No trace text, arguments, private addresses, injected prompts or account numbers were saved.

| Family | Baseline task 0/1 | Direct injection task 0/1 | Important-instructions injection task 0/1 |
| --- | --- | --- | --- |
| banking | 2 available | 2 available | 2 available |
| slack | 2 available | **0 available / 2 missing** | **0 available / 2 missing** |
| travel | 2 available | 2 available | 2 available |
| workspace | 2 available | 2 available | 2 available |

**20/24 available; 4/24 missing.** Verified directly against the pinned GitHub directory listings: the relevant Slack strategy directories contain `injection_task_1.json` through `injection_task_5.json` but **not** `injection_task_0.json`, for both selected user tasks. We do not fill those slots with `injection_task_1`: that would violate the earlier source-selection commit. Therefore the planned exposure composition is baseline 8, direct 8 and important-instructions 8; **observed availability** is baseline 8, direct 6, important-instructions 6, with missingness concentrated in Slack.

### Reproduction and threat model

```sh
python -m scripts.audit_agentdojo_strata
python -m scripts.audit_agentdojo_strata --check-upstream
python -m unittest discover -s tests -q
```

The first command checks the complete manifest against the preregistered 24-slot product offline. The second explicitly revisits **the same 24 source paths** at the immutable Git revision, verifies the SHA-256 and extracted tool names for available runs, and confirms missing-source statuses are still missing. The source reader caps each request at 64 KiB plus one overflow-detection byte and enforces a 1.5 MiB aggregate budget. `--capture-upstream` was used exactly once to create the metadata manifest and refuses to overwrite it. Validation fails if any case disappears, is reordered, changes attack condition, or claims unperformed reviewer work.

**Boundary:** the 24 planned runs are a **stratified exposure design**, not independent user grants. A missing attack run is neither a blocked attack nor a true negative. The 20 observed runs have no independently accepted simulated-scope reviews. All **24 simulated-scope reviews are pending/not_reviewed**; all **24 genuine human-approval labels are abstain**. There are **zero** trusted independent reviewers, zero policy verdicts and zero safety-accuracy estimates. A real blind-review study requires authorized independent reviewers and reviewed task sources; documenting a rubric is not itself a review.

**Next research gate (ATL-004H):** check independent task-source availability/privacy and prepare a redacted, source-pinned annotation packet + agreement calculator that fails closed without two real, distinct reviewers. Explicitly report missing/unknown cases and adjudication status; do not silently add a convenient Slack attack ID or claim population metrics.
