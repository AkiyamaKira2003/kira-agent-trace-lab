# OTLP/JSON interoperability with official generated Protobuf messages

**Campaign checkpoint:** ATL-004DH, 2026-11-22.
**Status:** VERIFIED_SOURCE_ONLY / NO_RUNTIME_CHANGE / NO_PRODUCTION_ATTESTATION.

## What was checked

Agent Trace Lab imports recorded OTLP/HTTP JSON execute_tool spans. Its previous fixtures were self-authored JSON. This proof uses generated messages from the official [opentelemetry-proto Python distribution](https://pypi.org/project/opentelemetry-proto/1.45.2/) (v1.45.2), converts them to regular Protobuf JSON using Google's official protobuf runtime (7.36.2 on KIRAA), then applies **only the trace/span ID encoding deviation required by OTLP/JSON**.

The [OTLP specification](https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding) says traceId and spanId byte arrays use case-insensitive **hex strings**, unlike regular [Protobuf JSON mapping](https://protobuf.dev/programming-guides/json/) which encodes bytes in **base64**. This is an intentional protocol difference, **not a bug** in Google's MessageToDict or in Agent Trace Lab's strict OTLP/JSON importer. Earlier historical proposals for base64 do not override the current normative specification.

The source-only runner [verify_otlp_protojson_sdk.py](../scripts/verify_otlp_protojson_sdk.py) creates a small original synthetic ExportTraceServiceRequest with two execute_tool spans in reverse arrival order, an unrelated span, omitted empty repeated resource/scope groups, and structured AnyValue with stringValue, intValue, doubleValue, boolValue, nested empty kvlistValue and arrayValue. It round-trips the message through binary Protobuf before converting to JSON.

## Reproduction on a fresh checkout

From repository root, using Python 3.12 (tested; the core package still supports Python 3.10+) and pip:

~~~powershell
python -m pip install --target artifacts/otlp_proto_sdk_1_45_2 opentelemetry-proto==1.45.2 protobuf==7.36.2
python scripts/verify_otlp_protojson_sdk.py
~~~

Both optional SDK dependencies reside in artifacts/, which is Git-ignored. The proof checks it loaded generated definitions from the pinned directory. Do **not** install this optional dependency into Agent Trace Lab's runtime package. The runner performs no network calls, trace exports, tool execution, or saved real-user imports; internet may be needed only for the initial pip download. No account credentials, production logs or grants are present in the fixture.

Its output is compact JSON statuses and hashes of synthetic data, not raw tool arguments. On 2026-11-22 using KIRAA/Python 3.12.10, generated definitions 1.45.2 and protobuf 7.36.2:

| Gate | Observed result |
| --- | --- |
| Official Protobuf SerializeToString and FromString round-trip | PASS |
| Generic Protobuf JSON with base64-encoded traceId | Rejected with SuiteError, as OTLP/JSON requires |
| OTLP-specific traceId/spanId hexadecimal conversion | PASS |
| SDK-omitted repeated fields for empty resource/scope groups | PASS |
| Nested AnyValue including omitted empty list/map | PASS |
| Two recorded tools sorted by timestamp, not source order | PASS, exact synthetic arguments |
| Schema 1.1 policy import | PASS, no invented task_authorization |
| Removed execute_tool spans | Rejected; no inferred empty safe trace |
| CLI import of valid generated OTLP/JSON | Exit 0; exact output and caller-provided label |
| CLI with invalid ID and synthetic private-marker argument | Exit 2; no output, traceback or marker echo |

Reproducible SHA-256 receipts for the original generated fixture:

- Binary Protobuf request: 96d6e025dd9fec47fa514c53fb87878a28e2f9294ca5d0007ad51a5b4da809ed
- Canonical sorted-key JSON after OTLP ID normalization: 00de56704c9b1b7cfe525bddcb5ec52135a288b92927ee08f99e72799cd0dcaa

## What this **does not** prove

This is official-generated-message interoperability after a manual, specification-required ID normalization; **not a captured HTTP/JSON request from a live OpenTelemetry exporter**. It is not evidence of compatibility with every exporter or OTLP revision, importing raw binary protobuf, actual end-user tool execution, live model behavior, or authenticated human authorization. The expected label remains explicitly caller-provided; successful import is not proof that an action was safe or approved.

The experiment found **no parser defect**. This optional source-only proof is not in default CI. CI success alone does not validate the optional SDK setup. No runtime dependency, production release, deployed website or protected-project change is implied.
