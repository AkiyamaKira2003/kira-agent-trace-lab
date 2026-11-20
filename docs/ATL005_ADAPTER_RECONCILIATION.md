# ATL-004Q — ATL-005 adapter evidence and release-gap reconciliation

**Scope:** reconcile the existing ATL-005 requirement ("Read-only adapter
for one real agent trace schema") with implemented and tested importers,
without building a duplicate adapter or claiming permission ground truth.

Baseline: KIRAA / KPC Core; C:\Projects\kira-agent-trace-lab;
original Git checkpoint 1c2d270, 2026-11-21.

## Already implemented — do not duplicate

| Prior work | Source and tests | Evidence | Still unverified |
| --- | --- | --- | --- |
| ATL-008, commit 7e8f841 | [OTLP importer](../agent_trace_lab/otlp.py), [tests](../tests/test_otlp.py), CLI import-otlp | Offline conversion of OTLP/HTTP JSON GenAI execute_tool spans; single trace ID, opt-in arguments, timestamp ordering, bounded input | Universal OTLP variants, concurrency causality, actual user consent |
| ATL-011, commit aa814ee; provenance ATL-012C | [SWE importer](../agent_trace_lab/swe.py), [tests](../tests/test_swe_import.py), CLI import-swe | Single recorded SWE-style row; externally pinned real benchmark action stream independently checked for **48** calls against original source Parquet columns | Whole-row/patch byte identity, actor permission, externally validated labels |
| ATL-004D, commit 9653280; later source pinning | [AgentDojo importer](../agent_trace_lab/agentdojo.py), [tests](../tests/test_agentdojo_import.py), CLI import-agentdojo | Single recorded run, assistant-only calls, unique IDs and bounds; later study includes **24 planned / 20 present / four missing** slots | Four missing Slack exposures, authenticated real-user grant labels or independent reviewers |

Each importer converts saved, recorded tool calls into a policy suite
**without executing tools or calling any model**. Expected allow/deny
labels are supplied by the caller and must not be inferred from
resolved/utility/security flags. CLI commands do intentionally write
requested JSON output which may contain sensitive arguments. "Read-only"
here means **no recorded actions executed**, not "no output written".
The latest stable v0.4.0 predates the development AgentDojo importer;
0.5.0.dev0 has not been promoted to stable.

## DoR/DoD decision matrix

| Requirement | Evidence and limits | Decision |
| --- | --- | --- |
| Convert a real tool-use trace schema without replay | Three independently merged importers; synthetic CLI tests and isolated wheel smoke; independent source-pinned SWE action verification | **IMPLEMENTED**; no duplicate ATL-005 adapter required |
| Correct source-constrained import | Strict supported envelopes; one pinned SWE action subset and selected AgentDojo runs independently verified | **PARTIAL** across formats, not universal support |
| ATL-004: independently authenticated task/grant evidence | No trusted human grants; reviewer abstentions remain | **BLOCKED**; cannot waive original prerequisite |
| ATL-006: representative externally labeled security evaluation | Existing self-authored or selected simulation labels do not establish independent ground truth | **BLOCKED**; no population precision or recall |
| ATL-007: qualified portfolio release/showcase | Reproducible CLI demo exists, but trustworthy authorization results and stable 0.5 release do not | **BLOCKED**; no KiraShop showcase change |

**Tracking decision:** ATL-005 is IMPLEMENTATION_VERIFIED /
ACCEPTANCE_BLOCKED (ATL-004), not NOT_STARTED or unqualified DONE.
ATL-004/006/007 retain their separate acceptance gates.

## Actual independent defect corrected during ATL-004Q

The OTLP nested kvlistValue parser previously formed error locations by
appending a user-controlled JSON key. A malformed nested AnyValue could
therefore echo a synthetic secret-like property name in CLI stderr.
The pre-fix leak was reproduced. The importer now uses the numeric
kvlistValue entry index for error locations, while preserving the exact
original key on successfully decoded data. Three tests cover invalid
nested values, valid argument-key preservation and a malformed CLI run.
This is a **bounded diagnostic privacy correction**, not complete PII
anonymization of recorded traces or normal reports.

## Verification

Run the relevant OTLP unit tests, all repository unit tests, isolated
development wheel installation/smoke, and the Windows/Ubuntu Python
3.10/3.12 CI matrix. A wheel build may fetch its declared setuptools
backend; installed-wheel smoke uses offline pip with no dependency fetch.
Test fixture agreement is not security efficacy.

**Next independent follow-up:** inspect whether CLI converter outputs
unexpectedly replace existing files or traverse output links. First
reproduce any actual issue and review current callers before changing
the output contract. Continue ATL-004/006 only when real external
authorization and reviewer evidence becomes available.
