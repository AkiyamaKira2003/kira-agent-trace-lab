# Real loopback OTLP/HTTP JSON export: official JavaScript SDK proof

**Campaign task:** ATL-004DI, 2026-11-22.
**Status:** VERIFIED_SYNTHETIC_LOOPBACK / NO_IMPORTER_BUG / NO_RUNTIME_DEPENDENCY.

## Purpose and safety boundary

The earlier [generated Protobuf proof](OTLP_PROTOJSON_SDK_PROOF_20261122.md) required converting ordinary Protobuf JSON trace IDs from base64 to hex. This independent test uses the **official JavaScript OTLP/HTTP JSON exporter** to transmit a genuine HTTP request to a one-shot receiver listening exclusively on 127.0.0.1 at an OS-selected ephemeral port. It captures the actual JSON bytes and verifies Agent Trace Lab imports the result **without changing any IDs**.

It is not a live AI-agent run, an external Collector, production instrumentation, remote traffic, human approval or actual tool execution. All spans and arguments are synthetic source constants. No owner application, customer data or protected project was accessed.

References: [OpenTelemetry JavaScript exporters](https://opentelemetry.io/docs/languages/js/exporters/), [official trace HTTP/JSON exporter module](https://open-telemetry.github.io/opentelemetry-js/modules/_opentelemetry_exporter-trace-otlp-http.html), [OTLP HTTP/JSON specification](https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding).

## Reproduction

From the Agent Trace Lab repository root, using Node 26.13.0 and Python 3.12.10 (the versions actually tested on KIRAA):

~~~powershell
npm install --no-save --ignore-scripts --no-audit --no-fund --prefix artifacts/atl004di_js_otlp_http '@opentelemetry/exporter-trace-otlp-http@0.300.0' '@opentelemetry/sdk-trace-node@2.12.0' '@opentelemetry/api@1.9.0' '@opentelemetry/resources@2.12.0'
npm ls --prefix artifacts/atl004di_js_otlp_http --depth 0
node --check scripts/verify_otlp_js_http_sdk.cjs
node scripts/verify_otlp_js_http_sdk.cjs capture_01
~~~

For another run, supply a new name such as capture_02 or capture_03. The script refuses to overwrite existing capture data. Optional npm packages and synthetic captures reside under Git-ignored artifacts/ only. No Python runtime package or production dependency changes. A package download may require internet initially, but the test emits only to local loopback.

**Version selection:** The most recent exporter at research time (0.301.2) declared OpenTelemetry API peer ^1.10.0 while sdk-trace-node 2.12.0 declared API >=1.0.0 <1.10.0. The initial install failed ERESOLVE. The pinned exporter 0.300.0 plus API 1.9.0 satisfied the tested combination and npm ls exited 0; npm emitted non-fatal peer-resolution/deprecation warnings. No force install or peer bypass was used. These proof-only versions are not a recommendation for live deployment.

The emitter intentionally specifies a synthetic service-name resource, deterministic nonzero trace/span IDs and timestamps, and a fixed synthetic header. It does not load private app instrumentation. The HTTP receiver rejects unexpected routes and authentication/cookie headers, limits body size to 512 KiB, and closes in finally. The exporter has bounded timeouts; no process remains after the run.

## Verified results

| Property | Observation |
| --- | --- |
| Receiver | 127.0.0.1, OS-assigned port, one POST to /v1/traces |
| Content-Type | application/json; no Content-Encoding |
| Spans received | 3: two synthetic execute_tool spans and one parent |
| Trace ID | 1234567890abcdef1234567890abcdef (32 hexadecimal digits) |
| First tool span ID | 0000000000000002 (16 hexadecimal digits) |
| Tool arguments | JSON strings inside OTLP stringValue attributes |
| Resource keys | Only service.name |
| Direct importer | 2 tools, files.read then docs.search, exact synthetic arguments |
| Caller label | deny preserved; no task_authorization fabricated |
| CLI valid capture | Exit 0, correct output |
| CLI invalid ID with private-marker argument | Exit 2, no output file, traceback or marker leak |
| No execute_tool trace | Rejected, not assumed safe |
| Receiver cleanup | No lingering owned Node/receiver process |

Independent repeat runs capture_02 and capture_03 generated exactly the same raw HTTP body SHA-256:

**6d3d3d49fa586ecc8cb8626b80484129ceb8240c3b24bdf3a30a6aeff514da3d**

Full captured JSON and request metadata remain in those Git-ignored folders on KIRAA. The receiver does not persist HTTP authentication headers. Never commit arbitrary real-world tool arguments or customer telemetry.

## What this does not prove

The check establishes one **real official JS exporter HTTP POST** with pinned local SDK versions. It does not establish behavior of every exporter, HTTP/protobuf or gRPC, compression, real AI agents, third-party telemetry, real-world security efficacy, or verified human authorization. The expected label remains caller-provided. Existing CI tests the Python package, **not the optional Node integration**, which was executed separately on KIRAA.

**Decision: no importer defect reproduced, therefore no runtime code modification.** Retain this source-only, reproducible regression proof; no new repository, release tag, website deployment or live service was created.
