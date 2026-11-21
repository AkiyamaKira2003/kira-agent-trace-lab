# ATL-004BN — Inspect approval is not execution or user consent

Status: **ADAPTER HOLD — source/spec validation only**, 2026-11-21.
KIRAA/KPC Core research. No actual Inspect user logs, prompts, tool arguments,
or private data were accessed. No real-world security effectiveness claim.

## Official contracts checked

1. [Inspect Tool Approval](https://inspect.aisi.org.uk/approval.html):
   In bridged agents, approval hands a call to a separate agent process; Inspect
   does NOT execute the scaffold's tools or necessarily record ToolEvent for
   them. An approved call may never run if another sibling call is rejected.
   Auto-approvals are not logged as visible approval decisions.
2. [Inspect event API](https://inspect.aisi.org.uk/reference/inspect_ai.event.html):
   ApprovalEvent fields include event, call, execution_id, approver, decision
   and modified. ToolEvent fields include id, execution_id, function,
   arguments, result and error. The execution_id is opaque, optional,
   **experimental**, absent in older logs, and for a bridge may refer to a
   proposed handout rather than actual execution.
3. [OpenTelemetry GenAI execute-tool conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/execute-tool.md):
   gen_ai.tool.call.id is conditional; tool arguments/results are opt-in.
   [Privacy guidance](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md)
   recommends not capturing sensitive content by default.
4. [Inspect AI license](https://github.com/UKGovernmentBEIS/inspect_ai/blob/main/LICENSE):
   MIT. A permissive source license does not grant rights to import private
   evaluation/operator/user logs.

## Existing Agent Trace Lab contract

- schema.py v1.1 case task_authorization holds task_id and single-use grants
  (grant_id, source_ref, tool, complete arguments); it validates structure,
  but source_ref is caller-supplied and not authenticated.
- engine.py matches observed trace events to unconsumed exact tool+arguments
  grants. It does not infer or verify the identity of the user's consent.
- otlp.py imports observed execute_tool spans when opt-in arguments are
  recorded; it does not import approval decisions or bridge execution.

## Original synthetic counterexample, reproduced on KIRAA

Using evaluate_suite() on fictional demo.tool with arguments
{"synthetic": true}:

| Data supplied to evaluator | Trace events | Actual verdict |
|---|---:|---|
| Approval record but no execution event | 0 | allow (no actions were supplied) |
| Naive adapter invents an executed action and a grant from approval | 1 | allow |
| A recorded action but no separately sourced grant | 1 | deny (TASK_GRANT_REQUIRED) |

These are real outputs from an original in-memory synthetic scenario, not
an Inspect evaluation. The second row demonstrates a **possible adapter-side
misrepresentation**, NOT a bug or security bypass in the existing evaluator.
An operator's approval is not itself the actual task user's permission.

## Safe design, blocked implementation

- ApprovalEvent is a **decision**, neither proof of execution nor an
  authenticated user grant. Never convert it to both a trace event and grant.
- For native calls, require an actual ToolEvent and unambiguous same-run
  correlation before claiming execution. If execution_id is present, match it
  as an opaque string; do not infer execution from approval.execution_id alone.
- For bridged agents' unobserved tool loop, no ToolEvent may exist. Without
  independently trusted execution telemetry, classify **unverifiable**.
- Reject ambiguous or missing IDs, repeated identifiers, rejected sibling
  calls, modified arguments, and old schema logs rather than guessing based
  on timestamps, tool names or model call IDs. For decision=modify, use only
  the effective approved call when trustworthy evidence supports it.
- A future adapter would be explicit opt-in, strictly bounded, metadata-only
  by default, and would not echo prompts, raw tool arguments or results.
- Before an authentic user authorization claim, require independently sourced
  evidence identifying the real user/task and the exact permitted action,
  plus consented and version-pinned sample data and independent review.

**Decision: NO GO** for an automatic Inspect-to-task-grant bridge or security
release based on these logs alone. The experimental schema does not reliably
identify executed bridged tools and does not attest user consent. No runtime
code was changed for this research. Investigate an authorized, reproducible
native-tool sample with both actual ToolEvent and approval evidence; if that
is unavailable, select another independently verifiable user-facing feature.
