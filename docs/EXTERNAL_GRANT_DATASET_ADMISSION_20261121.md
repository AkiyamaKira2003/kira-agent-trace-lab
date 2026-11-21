# ATL-004BA — external agent-action authorization dataset admission

Reviewed: 2026-11-21 (Asia/Ho_Chi_Minh). Owning source: existing KIRAA
`C:\Projects\kira-agent-trace-lab`, KPC Core. **Research-only, no external
trace downloaded, no user data published, no actions replayed.**

## Required evidence contract

An *independently qualified real-user authorization* label would need:

1. The original authentic user request and verifiable, task-bounded grant or
   denial, independent of the evaluated agent's response.
2. An immutable recorded action with tool, arguments, target and ordering, so
   exact scope can be compared to the grant.
3. At least two different independently authenticated reviewers, working
   blind to each other's judgments and publisher attack/outcome labels, plus
   supported adjudication and abstention on ambiguous cases.
4. A distribution right and privacy process for the underlying traces and
   review evidence. A repository license alone does not confer consent for
   redistributing personal call arguments.

## Three source-pinned candidates

| Candidate | Source / verified SPDX license | What its published schema supports | Missing for actual-user per-action authorization |
| --- | --- | --- | --- |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo/tree/089ed468cf3ed0322acc66b0211f26d9d90dbf60) | `089ed468cf3ed0322acc66b0211f26d9d90dbf60` / MIT | Simulated user-task `PROMPT`, `utility`, `ground_truth`, attack-task `security`, reference tool calls; already imported source-pinned subset in this repo | Reference calls and benchmark utility/security results are **not** independent human grants for every recorded argument/recipient; the existing fixed 24-slot sample has only 20 present traces and no independent reviewer acceptance |
| [AgentDrift](https://github.com/Asif-0209/AgentDrift/tree/014a514fa998b4ac4519579fceb8a5884b379bda) | `014a514fa998b4ac4519579fceb8a5884b379bda` / CC-BY-4.0 | 12,536 **synthetic** trajectories and step tags `benign`, `injection_point`, `hijacked`, `failed_injection`; two examples already adapted with attribution | Task-relative synthetic attack labels are not real-world user consent or reviewer-verified authorizations; `injection_point` alone is not an unauthorized action |
| [τ2-bench](https://github.com/sierra-research/tau2-bench/tree/835093c4ae1cc33cca3ba2995ea88c6c4441fe60) | `835093c4ae1cc33cca3ba2995ea88c6c4441fe60` / MIT | Simulated customer tasks, domain policies, user-agent conversations, tool actions and outcome scoring | Official docs say `evaluation_criteria.actions` is usually **one reference path**, not an exhaustive permission list; database/communication reward is not per-call authorization. A subset uses `RewardType.ACTION`, but that still makes a benchmark trajectory assumption, not a human-authenticated grant |

Source-schema references: [AgentDojo tasks](https://agentdojo.spylab.ai/concepts/task_suite_and_tasks/),
[AgentDrift readme](https://github.com/Asif-0209/AgentDrift),
[τ2 evaluation semantics](https://github.com/sierra-research/tau2-bench/blob/835093c4ae1cc33cca3ba2995ea88c6c4441fe60/docs/evaluation.md).
The pinned heads and SPDX ids were checked using the authenticated GitHub API,
not inferred from repository names. They are public source revisions, not
independent attestations of author identity or data consent.

## Decision

**NO QUALIFIED ADMISSION** for real-user, independently authenticated,
per-action authorization. Do not convert benchmark success, expected-tool
examples or synthetic hijack tags into these labels; keep all authentic-grant
adjudications **abstain**, and do not report real-world security accuracy,
precision, recall or user consent. The existing AgentDojo import and the
two-case attributed AgentDrift study remain valid at their *narrow stated
scope*. No duplicate importer or benchmark implementation is justified.

Revisit only when actual permission provenance, blinded independent review,
action-argument verification and legal/privacy checks can be demonstrated.
The next engineering work should be a separately qualified, conflict-free,
useful feature or product rather than another source-only evidence packet.
