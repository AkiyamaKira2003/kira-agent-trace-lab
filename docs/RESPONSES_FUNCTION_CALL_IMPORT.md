# ATL-004X — OpenAI Responses API function-call interoperability

**Scope:** one locally saved, completed Responses API JSON object.
The adapter extracts recorded function calls into an offline evaluator
suite. It does not send requests, execute functions, validate live
permissions or infer the caller's task.

## Source and differentiation

The official [OpenAI Responses API overview](https://developers.openai.com/blog/responses-api)
shows the polymorphic output item sequence: reasoning, message,
function_call. Function calls carry a name, call_id and a JSON-encoded
arguments string; their relative order is significant. The
[current API reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
defines the function-call object and response status. Sources
checked 2026-11-21. **This is format evidence, not a live API export
or independently validated security case.**

Previous adapters accept OTLP GenAI spans, SWE assistant
messages[].tool_calls, or AgentDojo messages[].tool_calls. None
consumes the single-response Responses API output array. This
adapter therefore serves a genuinely distinct interoperability need
without executing recorded actions or introducing a model dependency.
It does not support arbitrary agents/SDKs, Chat Completions, tool
outputs, streams or batched conversation histories.

## Strict bounded contract

- One local UTF-8 JSON file (max 2 MiB by the shared loader).
  Root status must equal completed; output must have 1..1000 items.
- Only completed function_call items with a name, a unique nonempty
  call_id (max 128 characters), and a JSON **string** of object-valued
  arguments are recorded, in original array order.
- Reasoning and ordinary message items are ignored. Unknown item
  shapes and hosted/computer/custom tool calls fail closed; they are
  never silently interpreted as evidence of no action.
- Empty traces, unfinished calls, duplicate IDs and invalid/oversized
  argument structures are rejected. Nested and duplicate JSON
  argument keys go through existing strict schema validation.
- A supplied schema 1.1 policy yields schema 1.1 output, **without**
  invented task_authorization entries. Missing trusted grants
  therefore still deny guarded actions.

The [self-authored synthetic example](../examples/responses_function_calls_synthetic.json)
contains two fictional calls named docs.search and files.read. It is
not copied from the OpenAI API, and it contains no user's prompts,
private metadata or model-generated results. Run it in a checkout:

    python -m agent_trace_lab import-responses examples/responses_function_calls_synthetic.json --policy-suite examples/suite.json --case-id fixture_example --expected allow --output artifacts/responses_fixture.json
    python -m agent_trace_lab evaluate artifacts/responses_fixture.json

The expected one-case matching synthetic verdict is **fixture
conformance**, not external benchmark performance, prompt-injection
detection or genuine user approval. The label is caller-provided,
never inferred from the response.

Output uses existing no-clobber file policy (exit 2 for an existing
path, --overwrite only by explicit request), first-write atomicity,
symlink safeguards and input-file protection. Imported arguments
remain in the output and **can contain PII, secrets or credentials**.
Review or redact before sharing, and retain real exports under
Git-ignored artifacts. The source MIT license does not confer
rights to redistribute third-party traces.
