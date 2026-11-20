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
