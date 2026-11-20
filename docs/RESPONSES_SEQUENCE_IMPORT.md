# ATL-004AF — bounded offline OpenAI Responses sequence importer

**Scope:** one **application-authored local JSON array** of complete,
individually saved OpenAI Responses API response objects, provided in
the order the caller wishes to inspect. This top-level array is **not**
an official OpenAI Responses API response envelope, batch result,
stream, or complete conversation export. No API access is required.

## Verified external contract and deliberately narrower local contract

The official [Responses API create/reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
defines an individual response and its output items, including
function_call objects with name, call_id and serialized JSON arguments.
The official [Responses migration guide](https://developers.openai.com/api/docs/guides/migrate-to-responses)
documents previous_response_id as **one** way of carrying context,
alongside manual history management and the Conversations API. The
reference and migration guide were checked on 2026-11-21.

No source establishes a **top-level array of response objects** as a
native endpoint payload. This project therefore supports it only as a
local, explicit research interchange format. Its declared order
reflects file-author ordering, **not proof of authentic temporal
order, provenance, tool execution or human authorization**.

## Accepted and rejected shapes

- UTF-8 local JSON array with 1..50 entries, at most 2 MiB via
  the existing size-limited strict JSON loader (duplicate JSON keys
  and non-JSON numbers rejected).
- Every entry must be a response object with unique nonempty id
  (max 128 chars), status completed and an output array of 1..1000
  items. Total output items across all responses <= 10,000.
- If previous_response_id is present and non-null, it must
  **exactly** match the immediately preceding array entry's id.
  The first response cannot declare a non-null previous_response_id.
  Absent/null links are permitted for manually managed history but
  make no continuity guarantees.
- Only completed function_call output items are extracted.
  They must have a nonempty name, globally unique nonempty call_id
  (max 128 chars), and arguments encoded as a JSON-object **string**;
  existing nested-argument and exact-policy checks still apply.
  Duplicate call IDs fail even if they are in different responses.
- Ordinary message and reasoning output items do not become actions.
  A response containing only messages can occur between calls;
  across the entire archive, **at least one function_call is required**.
- Unknown, hosted, computer, custom, MCP, output/input-event and
  stream-item types are rejected, never silently treated as no action.
  Incomplete responses/calls and incorrect linkages are rejected.
- At most 10,000 recorded calls can reach the single combined suite
  case. No grants, authorization labels, model responses, or tool
  result values are synthesized. The --expected label is explicitly
  supplied by the operator and **is not verified**.

## Reproducible self-authored example

The [fixture](../examples/responses_sequence_synthetic.json) has three
fictional completed responses (search, message-only, file read)
with two unique call IDs and matching explicit local links. It is
**not** a captured request, external benchmark or genuine grant.

    python -m agent_trace_lab import-responses-sequence examples/responses_sequence_synthetic.json --policy-suite examples/suite.json --case-id local_sequence --expected allow --output artifacts/local_sequence.json
    python -m agent_trace_lab evaluate artifacts/local_sequence.json --summary-only

The command only copies and validates *recorded* function names and
arguments. It never runs tool functions or contacts a service.
Imported arguments may include personal data or credentials and must
be reviewed/redacted before public sharing. The same existing
importer no-clobber and --overwrite opt-in atomic publication guards
apply; the source archive and original policy suite are protected.
Source-only tests and installed-wheel smoke verify order, strict
validation, privacy diagnostics and backward compatibility with the
single-response import.

**Remaining research gates:** no independently authenticated
human task-grants, no two independently authenticated reviewers,
no representative externally labeled safety population, no qualified
security-product or KiraShop integration. Matching fictional fixture
labels is not empirical safety performance.
