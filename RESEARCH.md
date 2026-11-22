# Research and differentiation

Research date **2026-11-20 (Asia/Ho_Chi_Minh)**. Sources below were checked as representative alternatives; this is not a complete Internet survey. No external code was copied.

| Source | Existing capability | License at research time | Relevance |
| --- | --- | --- | --- |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | Evaluation tasks, model/agent runners, scoring | MIT | Reproducibility reference; this lab has no model runner. |
| [AgentDojo](https://github.com/ethz-spylab/agentdojo) | Dynamic environment for AI-agent attacks and defenses | MIT | Action-level evaluation motivation; this lab has no dynamic attack simulation. |
| [Promptfoo](https://github.com/promptfoo/promptfoo) | Prompt/agent evaluation and automated red-teaming | MIT | Full-featured alternative; this lab intentionally has a narrower stdlib-only contract. |
| [OWASP AISVS research](https://github.com/OWASP/AISVS) | AI application security guidance | Verify upstream before reuse | Trust boundaries and least-privilege principles, not proof this tool blocks attacks. |
| [OpenTelemetry GenAI execute-tool](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/execute-tool.md) | Standard tool-execution spans with optional recorded arguments | Refer to upstream | Import of a restricted OTLP JSON format; arguments are opt-in and can contain sensitive data. |
| [AgentDrift](https://github.com/Asif-0209/AgentDrift) | Independently authored **synthetic** trajectories with per-step benign/hijacked labels | CC BY 4.0 data | Demonstrates a task-authorization semantic gap that a tool-name allowlist cannot close. See docs/EXTERNAL_CASE_STUDY.md; source labels differ from our policy verdicts. |

**Research hypothesis:** A deterministic, inspectable checker of *recorded tool actions* may be useful as a low-cost CI assertion, especially where model-based graders produce variable results. Its limits are deliberate: no LLMs, no callbacks, no network calls, no automatic attacks, no inferred hidden actions.

**Why a separate repo?** A standalone Python CLI/library has clear product and dependency boundaries from KiraShop's React UI or its Sudoku generator. Integration into the portfolio is deferred until independent evidence is stronger.

**Selection rubric:** depth /20, usefulness /20, differentiation /15, portfolio demonstration /15, feasibility /10, learning /10, maintainability /10. Scores are *prospective engineering assessments*, not experimentally measured quality:

| Candidate | Depth | Useful | Distinct | Demo | Feasible | Learn | Maintain | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Offline AI-agent trace boundary evaluator | 16 | 17 | 11 | 13 | 9 | 9 | 9 | **84** |
| More statistical QA for KiraShop Sudoku | 15 | 16 | 9 | 14 | 10 | 8 | 8 | **80** |
| Browser performance instrumentation for Motion Lab | 12 | 15 | 8 | 11 | 10 | 7 | 9 | **72** |

Priority uncertainty: the evaluator's utility depends on ingesting authentic real-world traces and evaluating independently labeled behavior. If a mature framework already solves that exact use case more economically, contribute upstream rather than maintaining an unnecessary standalone project.

**2026-11-22 product-value triage:** [ATL-004DM](docs/PRODUCT_VALUE_TRIAGE_20261122.md) compares current Phoenix/Langfuse capabilities with an actual reproducible CLI workflow gap (unlabeled OTLP policy inspection). [Issue #72](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/issues/72) is a *hypothesis to test*, not evidence of user demand, competitive superiority or validated real-world security outcomes.

**Follow-up:** research a stable trace schema, build a read-only adapter, use independently labeled benign and harmful cases, measure false positives/negatives, then compare results against existing frameworks. No external licenses are inherited by mere research links.

OpenTelemetry was chosen for the first adapter because its documented attributes are framework-neutral. The resulting converter handles one trace ID at a time and rejects missing arguments or ambiguous ordering metadata rather than guessing; tests only use synthetic spans until a real, consented dataset is available.
