# ATL-004B — external label provenance and authorization review

**Research date:** 2026-11-20 (Asia/Ho_Chi_Minh).
**Scope:** distinguish an external author's *synthetic-scenario* annotation from a genuine, independently verified user authorization. No raw prompts, conversations, tool arguments or benchmark patches are republished.

## Three different questions

| Field | Meaning | Evidence requirement |
| --- | --- | --- |
| Scenario label | Did the benchmark author call the recorded synthetic sequence benign or hijacked relative to a simulated request? | Source-pinned author annotations and a declared mapping rule |
| Human authorization label | Did an independently authenticated principal authorize the exact action, resource, scope and time? | Trusted user task and issued grant evidence, independently linked to trace events |
| Static policy verdict | Does the observed action obey the local policy provided to the evaluator? | Recorded calls and validated policy, with no assumption about user intent |

These fields are **not interchangeable**. An independently authored synthetic attack label is not an independently authenticated production-user approval. NVIDIA Open-SWE-Traces has a task-success field named resolved; it is not an authorization label.

## Two source-reviewed examples

Source: [Asif-0209/AgentDrift](https://github.com/Asif-0209/AgentDrift) by Asif Pinjari and Mithun Paul Saint-Germain, commit [014a514fa998b4ac4519579fceb8a5884b379bda](https://github.com/Asif-0209/AgentDrift/tree/014a514fa998b4ac4519579fceb8a5884b379bda). **Dataset license: CC BY 4.0.** Records are synthetic and independently step-labeled; they are not consented production traces.

| Case | Pinned file | Author step labels | Scenario label | Verified human authorization |
| --- | --- | --- | --- | --- |
| banking_benign_0353 | [test_00000](https://github.com/Asif-0209/AgentDrift/blob/014a514fa998b4ac4519579fceb8a5884b379bda/data/test/test_00000.json) | 4 benign | allow | **abstain** |
| email_attacked_full_0217 | [test_00001](https://github.com/Asif-0209/AgentDrift/blob/014a514fa998b4ac4519579fceb8a5884b379bda/data/test/test_00001.json) | 3 benign; 1 injection_point; 2 hijacked | deny | **abstain** |

The two record identities, SHA-256 source digests, rights, step annotations and explicit abstentions are stored in [authorization_label_review.json](authorization_label_review.json). The bounded, opt-in [verifier](../scripts/verify_label_review.py) fetches only these two pinned source JSON records, checks the source hashes and annotations and **rejects any attempt to present the synthetic labels as human consent**.

This is a metadata/annotation audit, not a new corpus. The two source-derived label annotations are attributed to AgentDrift under CC BY 4.0; the verification program and tests are original code under the repository's MIT license. The publisher does not endorse this adaptation.

## Review protocol for future real-user authorization labels

1. **Principal/task provenance:** independently establish actor identity, the original user request and task ID; text created by the agent, a web page, or a tool response cannot assert consent.
2. **Exact authorized scope:** record the tool, resource/recipient, argument constraints, and allowed task duration before inspecting model verdicts; establish explicit delegation and revocation rules.
3. **Grant issuance and binding:** obtain trusted, tamper-evident approval records and an independent correlation between the grant and the executed action. An unauthenticated free-form source_ref cannot establish consent.
4. **Three-way decision:** mark allow only for a verified matching approval; deny only when a trusted, complete authorization ledger or explicit policy independently proves the action outside scope; **otherwise abstain**.
5. **Blind, independent review:** at least two reviewers assess provenance without seeing this evaluator's verdict. Resolve disagreements through cited evidence or abstain.
6. **Rights and privacy:** pin source revision, verify applicable license, ensure personal data was authorized for sharing and redact before any public artifact; keep raw records in ignored local storage.
7. **Metrics integrity:** scenario adherence and verified human authorization have different denominators. Always disclose abstentions, sample selection and class balance. Never compute real-user authorization precision/recall from these two synthetic selected cases.

A controlled test harness may define **simulated-task authority** (a legitimate simulated user task versus an attacker goal), but must not label this real-world consent. A missing grant in a sparse log is not by itself a verified denial unless a complete trusted default-deny approval process exists.

## Research alternatives

| Candidate | Supported use | Unresolved gate |
| --- | --- | --- |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo), [NeurIPS 2024](https://arxiv.org/abs/2406.13352) | MIT-licensed benchmark framework defines legitimate user goals and separate attacker goals; possible simulated-task boundary measurements | Pin specific recorded run, check rights of artifacts and reproduce actual tool calls; not proof of real-user consent |
| [Authorization Drift Benchmark](https://arxiv.org/abs/2611.09113), Cao et al., published 2026-11-06 | Paper frames overreach along data/tool/scope/time dimensions and reports 648 task cases across seven domains | Concrete dataset license, accessible pinned records and independent replay **not yet verified** |
| [NVIDIA Open-SWE-Traces](https://huggingface.co/datasets/nvidia/Open-SWE-Traces) | A recorded 48-tool-call benchmark run was independently imported from pinned Parquet actions | Issue resolution is not approval; no human-grant labels |

**Decision:** two independent *scenario* labels verified, **zero authentic human-grant labels**. This completes ATL-004B evidence classification only. ATL-004 and ATL-006 remain open.

## Reproduce

Run from repository root:

    python -m scripts.verify_label_review docs/authorization_label_review.json
    python -m scripts.verify_label_review docs/authorization_label_review.json --check-upstream
    python -m unittest discover -s tests -q

The offline manifest check and optional 16 KiB-per-source upstream recheck must show 1 scenario allow, 1 scenario deny, 2 human-authorization abstentions and 0 eligible cases for real-user authorization metrics. No recorded actions are executed.

**NEXT_ACTION (ATL-004C):** Pin a small AgentDojo run with an explicit simulated legitimate task, attack objective and observed tool calls. Verify specific file rights and derive a simulated-task-boundary fixture with independent labels, privacy controls and transparent abstentions. If source rights/records cannot be established, document the blocker instead of inventing metrics.
