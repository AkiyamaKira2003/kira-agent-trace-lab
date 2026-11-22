# ATL-004DK — two real OTLP/HTTP JSON POSTs, one recorded trace

**Decision (2026-11-22): `VERIFIED_SYNTHETIC_MULTIPOST / DOCUMENTED_COMPLETENESS_BOUNDARY / NO_PARSER_BUG`.** This is a source-only research check, **not** a complete agent recorder, human authorization proof, production security feature or release.

## User-facing question and explicit contract

The official OpenTelemetry JavaScript OTLP HTTP exporter may emit separate batches from one trace. Agent Trace Lab's `import-otlp` takes **one complete OTLP/JSON export object per invocation**. Can a consumer infer that its first valid HTTP request contains the entire trace? **No.** The SDK may export additional tool spans later. The first request is independently valid, and the importer has no end-of-trace marker, batch count or external record of what was captured. It cannot prove completeness from one JSON object.

This is a capture/transport completeness boundary, **not a parser bug or evidence of runtime tool execution**. Supplying a list of two raw export envelopes is currently rejected instead of silently interpreted as a complete run. A caller may explicitly assemble the `resourceSpans` arrays of *already captured, bounded, trusted-to-be-complete* envelopes into one OTLP export object, then apply the existing single-trace, ID, no-empty-tool and duplicate-span validation. That assembly is a temporary workflow for locally controlled input, **not** an authenticated or production-safe ingestion protocol. The input may still be missing POSTs, including missing tool calls. Never treat its allow/deny result as confirmed user permission or security efficacy.

## Repeatable experiment

On KIRAA, Node 26.13.0, Python 3.12.10. The prior [official JS SDK proof](OTLP_JS_HTTP_EXPORTER_PROOF_20261122.md) documents pinning optional packages *only* under the ignored `artifacts/atl004di_js_otlp_http/node_modules` directory:

```powershell
node --check scripts/verify_otlp_js_http_multi_post.cjs
node scripts/verify_otlp_js_http_multi_post.cjs batch_01
node scripts/verify_otlp_js_http_multi_post.cjs batch_02
python -m unittest tests.test_otlp.OtlpTests.test_explicit_two_export_envelopes_require_external_completion_contract -v
```

The script checks the previously pinned package versions (`@opentelemetry/api@1.9.0`, `sdk-trace-node@2.12.0`, `exporter-trace-otlp-http@0.300.0`, `resources@2.12.0`) rather than installing any new runtime dependency. It runs one self-authored parent span and two `gen_ai.operation.name=execute_tool` child spans, forcing a bounded exporter flush after each child. One real SDK HTTP POST is observed before the second tool span is created, then a second POST is observed after the parent ends. HTTP listening is limited to `127.0.0.1` on an ephemeral port, request payloads are capped at 512 KiB, credentials/cookies are rejected, and the server and provider shut down in `finally`.

For each new run name the script refuses to replace existing evidence. JSON and a small metadata receipt are saved **only** under the ignored `artifacts/atl004dk_multi_post_20261122/batch_XX/`. The tool calls are synthetic strings; nothing recorded is executed and no owner application, external Collector, network destination, customer trace or private key is involved. Captures/arguments are not intended for GitHub.

## Actual local observations

| Control | Actual result |
| --- | --- |
| Official exporter transport | Exactly **2** HTTP POST `/v1/traces`, content type `application/json`; same nonzero 32-hex trace ID, distinct span IDs |
| First HTTP JSON object | `import_otlp` and the source-checkout CLI accept **1** recorded `files.read` call; cannot infer missing later `docs.search` |
| Second HTTP JSON object | Contains and imports **1** `docs.search` call, still using same synthetic trace ID |
| Array of two envelopes | Rejected as an invalid top-level export object; not silently accepted or merged |
| Explicit assembly of both `resourceSpans` arrays | Imports **2** ordered tool calls; `expected=deny` remains the caller's label; no `task_authorization` fabricated |
| Replayed tool span ID across envelope boundary | Explicit assembled input fails with CLI exit **2**, no output file or traceback |
| Python negative/positive unit test | One new test covers per-envelope behavior, explicit assembly, wrong trace ID, duplicate span and rejected list |

Two independent SDK process runs (`batch_01`, `batch_02`) produced identical **raw HTTP request-body** hashes:

- POST 1 SHA-256: `09735caf8ae2ff837e3e231a6c9d3825e6b2b743522b8ce6138a020e0bd7c6bd`
- POST 2 SHA-256: `ca8a4ef81efbc76c241f9ded9ee5c8d59befae4c8c366aad0c03d6a229a01315`

Those hashes prove repeatable original *synthetic HTTP bytes* on this tested setup, not integrity/authenticity for outside traces. The Python unit fixture is separately synthetic and must not be counted as a third official exporter test. The optional Node proof is manual/source-only, not part of installed Python wheels or the default GitHub Actions matrix.

## Safe path to a real multi-request importer (not implemented here)

An external collector/capture layer should establish **positive completeness evidence** before submitting one trace: a bounded allowed request count and bytes, one capture/session identity, all expected POSTs or an authenticated end marker, timeouts and explicit incomplete/aborted status, duplicate/replay detection, traceId consistency and deterministic ordering. It must reject an incomplete set instead of evaluating a possibly truncated sequence as if fully observed. The pure importer can then validate the assembled object. Merely accepting `list[OTLP export]` in `import_otlp` would not solve silent loss when some requests were never captured; do not add that shortcut without a capture protocol.

**Release boundary:** No new runtime feature, GitHub release, production receiver, credential, published benchmark, KiraShop change or validated security product. Independent authenticated user authorization and representative human labels remain `HOLD`.
