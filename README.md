# Kira Agent Trace Lab

**Offline, deterministic evaluation of tool-using AI-agent traces.** This Python prototype evaluates recorded tool calls against an explicit allowlist policy. It never executes those calls or invokes a model.

> This is a research prototype, not a sandbox, runtime authorization mechanism, prompt-injection detector or proof of an agent's security.

## Quick start

Python 3.10+, no runtime dependencies, network access or model API keys required:

Clone the [source repository](https://github.com/AkiyamaKira2003/kira-agent-trace-lab) and run these commands from its root to use the included examples. Alternatively, install the wheel attached to the [v0.4.0 GitHub release](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.4.0) with `python -m pip install ./kira_agent_trace_lab-0.4.0-py3-none-any.whl`; example JSON files are still in the source repository. **This project does not claim a PyPI distribution.**

For the newer four-format importers and policy comparison CLI, see the
[v0.5.0.dev0 research-only GitHub prerelease](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.5.0.dev0).
Install the attached experimental wheel with
`python -m pip install ./kira_agent_trace_lab-0.5.0.dev0-py3-none-any.whl`.
Verify the artifact against its attached SHA256SUMS.txt. This **does not**
replace v0.4.0 as latest stable, establish real-user authorization
labels or qualify any security-product claims.

The newer [v0.5.0.dev1 research-only GitHub prerelease](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.5.0.dev1)
includes five import commands across four trace-format families,
safe saved reports and privacy-limited summary options. Install its
**actual attached wheel** with
`python -m pip install ./kira_agent_trace_lab-0.5.0.dev1-py3-none-any.whl`
after verifying the release's SHA256SUMS.txt, rather than assuming
that rebuilding the current development branch reproduces the tag.
The [published dev1 research notes](docs/RELEASE_NOTES_V050_DEV1.md)
and [evidence gate](docs/RELEASE_GATE_004AI.md) explicitly retain all
unverified real-user grants and external security-review conditions.
Both dev0 and dev1 remain prereleases; v0.4.0 is still Latest stable.

A source-distribution archive (.tar.gz) is an **installable code-only
artifact**, not a substitute for cloning the Git repository: it intentionally
excludes tests that require fixtures, research scripts and docs, adapted
CC BY 4.0 examples, and any ignored private trace artifacts. For
reproducible research examples and test execution, use the repository
checkout, not the source archive. See the
[source archive safety check](docs/SOURCE_SDIST_QA.md).

```sh
python -m agent_trace_lab evaluate examples/suite.json
python -m agent_trace_lab evaluate examples/suite.json --format json
python -m agent_trace_lab evaluate examples/suite.json --format json --output artifacts/report.json
python -m agent_trace_lab evaluate examples/suite.json --summary-only --format json
python -m unittest discover -s tests -v
```

For sharing a **counts-only** evaluation without case IDs, tool names,
argument values or individual violations, use `--summary-only` with
`--format json` or `--format text`. The JSON report declares
the labels **caller-supplied and not independently verified**, and
does not include accuracy, precision or recall estimates. A mismatch
still returns exit **1**. This does not anonymize original input
files or prove real-world agent security effectiveness.

When writing an evaluation report, **--output only creates a new
file**. If it already exists, the CLI returns exit **2** without
replacing it. To deliberately replace an existing regular report:

```sh
python -m agent_trace_lab evaluate examples/suite.json --format json --output artifacts/report.json --overwrite
```

Report publishing uses a complete temporary write and an atomic
commit; it refuses to overwrite the input suite or follow a symbolic
link as a report target. A saved report still returns exit **1** when
its synthetic expected labels do not match policy verdicts. Output
contents can carry case identifiers; the write safeguards do not
anonymize them.

Exit **0** means all expected case labels matched, **1** means at least one mismatch, and **2** means invalid input/I/O failure. The same input yields the same report.

Malformed inputs are rejected with bounded, [privacy-conscious schema
diagnostics](docs/ERROR_DIAGNOSTIC_REDACTION.md). Unexpected JSON property
names and invalid tool identifiers are **not echoed in validation error
messages**. Invalid JSON/UTF-8 and filesystem errors are reported
using a bounded error category without echoing source paths, private
destination names, or raw parser exception text. This applies to
installed evaluate, compare-policies, and all five import commands.
Normal reports and imported private trace files can still
contain user-supplied identifiers and values; this is not a complete
anonymization feature.

The [ATL-005 adapter reconciliation](docs/ATL005_ADAPTER_RECONCILIATION.md)
maps the already-implemented OTLP, SWE and AgentDojo importers to the
original read-only trace-adapter objective. Independent task-authorization
evidence and externally labeled security metrics remain unmet release gates.

The [v0.5 research release gate](docs/RELEASE_GATE_V05_RESEARCH.md)
documents which packaging, licensing, execution and evidence checks
are verified and which remain on hold. The development version is not
an independently validated security product or a stable v0.5 release.
The [v0.5.0.dev0 research-only prerelease notes](docs/RELEASE_NOTES_V050_DEV0.md)
separate verified installation and static-policy features from
unverified real-user grant and independent security-evaluation gates.

The included synthetic example yields **8/8 labeled matches** with TP=5 and TN=3. **This is a smoke test, not an independently measured agent-safety score.**

### Two-policy demo: a deliberate mismatch and a task-scoped alternative

The [self-authored CLI contrast](docs/POLICY_CONTRAST_DEMO.md) uses the same
fictional unrequested email-forward action under two policies. A permissive
tool-name allowlist **allows** it and intentionally exits **1** because the
synthetic case label expects denial. A task-scoped schema 1.1 policy **denies**
it without an exact-action grant, while also demonstrating a matching
fictional grant, recipient redirect, one-time grant consumption, and a normal
search. All five schema 1.1 cases match their **self-authored** labels.

```sh
python -m agent_trace_lab evaluate examples/demo_permissive.json
python -m agent_trace_lab evaluate examples/demo_task_scoped.json
```

To compare **the exact same recorded case** under those two policies,
without pretending two suites contain identical scenario sets, use:

```sh
python -m agent_trace_lab compare-policies examples/demo_permissive.json --candidate-policy examples/compare_candidate_task_guarded.json --format json
```

The baseline file supplies the recorded cases and original policy;
the candidate file contains only schema_version and policy. The CLI
returns changed decisions, not accuracy or precision/recall scores.
The fictional unrequested forward changes from allow to deny solely
because the candidate requires a task grant. This comparison does
**not** authenticate user consent or modify any source file.
To share a decision-only report without exposing case identifiers,
append **--redact-case-ids**. It replaces case IDs with stable
per-report ordinal aliases such as case_0001 while preserving decisions.
This is **case-ID pseudonymization**, not anonymization of arbitrary
trace contents, file paths or diagnostic errors.
To save the same text/JSON report safely instead of writing it to
stdout, pass `--output artifacts/policy_delta.json` (the
destination must be new). Repeating the operation on the same path
returns exit **2** without replacing data. Use `--overwrite`
only when deliberate replacement of an existing regular file is
intended. Both the baseline suite and candidate policy are protected,
and `--redact-case-ids` also applies to saved reports:

```sh
python -m agent_trace_lab compare-policies examples/demo_permissive.json --candidate-policy examples/compare_candidate_task_guarded.json --format json --redact-case-ids --output artifacts/policy_delta.json
```

The report shows **policy decision changes, not externally validated
security or human-authorization accuracy**. Saved outputs are
committed atomically; original inputs are not modified.
See the [policy delta verification](docs/POLICY_CONTRAST_DEMO.md).

To verify these exact outcomes from an isolated installed development wheel,
run `python -m scripts.verify_installed_wheel --wheel-dir artifacts/qa-demo-wheel`
after building the wheel as documented in the [demo instructions](docs/POLICY_CONTRAST_DEMO.md).
The smoke gate additionally checks the installed `agent-trace-lab` console
launcher against module invocation on the same fictional inputs.
Neither a fictional grant nor fixture-label agreement is authenticated user
consent or evidence of real-world protection.

### External counterexample (deliberate mismatch)

An attributed two-case [AgentDrift external case study](docs/EXTERNAL_CASE_STUDY.md) demonstrates that tool-name allowlists **cannot infer user-task authorization**. The third-party, independently labeled *synthetic* corpus includes a hijacked email-forward/delete sequence. With an intentionally permissive policy, this evaluator still **allows** it: the example exits **1**, exposing the expected *semantic coverage gap* rather than hiding it behind a perfect synthetic score.

```sh
python -m agent_trace_lab evaluate examples/agentdrift_counterexamples.json
```

The two adapted data records are **CC BY 4.0**, not MIT; source, authors, license and modifications are recorded in the case study. This two-record sample is **not** a population estimate or a representative attack-detection benchmark.

An additional [independent-label provenance review](docs/INDEPENDENT_AUTHORIZATION_LABELING.md) distinguishes external authors' synthetic scenario labels from authenticated user grants. Its optional, bounded source checker verifies two upstream record hashes and step annotations. Both records **abstain** from real human-authorization judgments and are **ineligible** for real-world authorization precision/recall metrics.

A separate [pinned AgentDojo task-boundary case study](docs/AGENTDOJO_SIMULATED_BOUNDARY.md) independently verifies one benign and one attacked **recorded** run against the original benchmark's task definitions. The attacked run includes an extra send-email action outside the simulated user's calendar lookup request. This is one selected simulation case, **not** authenticated human consent or a measured safety rate.

## Task-bound grant matching (v0.3, opt-in)

Schema **1.1** adds an optional task-authorization audit for selected high-impact tools while preserving schema **1.0**. An auditor supplies independent exact-action grant records for a case; the checker rejects guarded calls without a matching, unconsumed grant.

```sh
python -m agent_trace_lab evaluate examples/task_grants.json
```

The 9-case, **self-authored** example covers a legitimate forward, an unexpected recipient, missing grant, unauthorized deletion, duplicate execution, separate approvals for repeated calls, ordinary search, approved deletion and extra arguments. Test outcomes are fixture conformance, **not independently measured permission accuracy**.

In a 1.1 policy, `task_guarded_tools` names must already be in the tool allowlist. Each 1.1 case can include `task_authorization` with a `task_id` and `grants`. Each grant includes a unique `grant_id`, opaque `source_ref` evidence reference, a `tool` and the exact JSON `arguments`. Object field ordering is ignored, but argument values, types, lists and additional fields must match; each grant is consumable once per recorded trace. Missing grants deny guarded calls by default and do not loosen pre-existing policy restrictions.

**Security boundary:** this offline evaluator **does not authenticate the user, validate source_ref or prove that a grant was genuinely issued**. A malicious party could fabricate a matching grant if permitted to author the suite. A separate trusted system must establish and protect actual approval evidence. Never use these evaluation results as authorization to execute real tools. See the [design and threat model](docs/TASK_AUTHORIZATION_DESIGN.md).

All recorded trace import commands (OTLP, SWE, AgentDojo, single Responses
and local Responses sequence) refuse to
overwrite an existing output file by default. To repeat an import to
the same destination, use a new filename or explicitly pass
**--overwrite**. The opt-in replacement is atomic for regular files
and refuses symbolic-link destinations; see
[import output safety](docs/IMPORT_OUTPUT_SAFETY.md).
The initial write is also committed only after the complete JSON
has been written to a private temporary file. Filesystems that do not
support hardlinks fail closed instead of exposing partial output.

## OpenAI Responses API function-call output import (development main)

The optional import-responses converter reads **one locally saved, completed
Responses API response JSON object**. It imports ordered function_call items
inside the top-level output array, using their name and JSON-string arguments.
It ignores ordinary assistant messages and reasoning items, but rejects
unsupported hosted tool calls rather than treating them as a clean trace.
Streaming events, full conversation histories and Chat Completions tool_calls
are outside the supported envelope.

    python -m agent_trace_lab import-responses examples/responses_function_calls_synthetic.json --policy-suite examples/suite.json --case-id synthetic_responses --expected allow --output artifacts/responses_imported.json
    python -m agent_trace_lab evaluate artifacts/responses_imported.json

For an application-authored **ordered JSON array of saved completed
Responses objects**, use the separate import-responses-sequence command.
The array is **not a native OpenAI API batch-response envelope**.
The importer keeps complete function calls in declared array order,
rejects duplicate response and function call IDs and rejects mismatched
explicit previous_response_id links. An absent link does not prove
causal connection or human approval. The entire archive is bounded
to 2 MiB, 1–50 responses and at most 10,000 output items:

    python -m agent_trace_lab import-responses-sequence examples/responses_sequence_synthetic.json --policy-suite examples/suite.json --case-id synthetic_sequence --expected allow --output artifacts/responses_sequence_imported.json
    python -m agent_trace_lab evaluate artifacts/responses_sequence_imported.json

See [the exact sequence archive contract](docs/RESPONSES_SEQUENCE_IMPORT.md).

The fixture is entirely **self-authored** from the documented API shape;
it is not a recorded user/model run. The expected label is caller-supplied,
not independently authenticated. No API request, model call or recorded
function execution occurs. Exported arguments can contain sensitive
information; keep real imports private. See the
[format scope and upstream sources](docs/RESPONSES_FUNCTION_CALL_IMPORT.md).

## Import OpenTelemetry tool traces (v0.2)

The converter accepts a saved **OTLP/HTTP JSON** export using OpenTelemetry's GenAI execute-tool span attributes: `gen_ai.operation.name=execute_tool`, `gen_ai.tool.name`, and opt-in `gen_ai.tool.call.arguments`. Supported argument formats are JSON-object strings or a limited structured OTLP `kvlistValue`.

```sh
python -m agent_trace_lab import-otlp examples/otlp_spans.json --policy-suite examples/suite.json --case-id local_trace_01 --expected allow --output artifacts/imported.json
python -m agent_trace_lab evaluate artifacts/imported.json
```

The **expected label is supplied by the person running the import**. No ground truth is inferred from the trace. Import refuses missing arguments, invalid data, unrelated trace IDs and missing timestamps. Events within one trace are ordered by `startTimeUnixNano`; simultaneous operations may still be causally unordered. The converter cannot infer which human task those spans belong to.

When importing with a schema-1.1 policy, the resulting suite also uses 1.1 but contains **no fabricated task authorization**. Guarded actions therefore deny unless a trusted source supplies grants separately.

**Privacy:** Imported suites retain tool argument values, which can contain secrets and PII. The CLI makes no external requests and reports omit argument values, but **never commit imported real-world suites without reviewing/redacting them**. Use `artifacts/` for locally generated examples (ignored by Git).

This is a narrow OTLP JSON import, not support for binary protobuf, all exporters, all semantic-convention versions or model-specific logging formats.

## Experimental SWE recorded tool-call import (v0.4)

An offline, **experimental** importer reads a single locally saved SWE-agent-style JSON row containing `messages`. It extracts assistant `tool_calls[].function` records only, without executing tools, including the original system prompt, or using the dataset's `resolved` task-success field as an authorization label.

```sh
python -m agent_trace_lab import-swe examples/swe_recorded_row_synthetic.json --policy-suite examples/swe_structural_policy.json --case-id synthetic_run --expected allow --output artifacts/swe_imported.json
python -m agent_trace_lab evaluate artifacts/swe_imported.json
```

Both inputs are **self-authored synthetic structural fixtures**, not copied benchmark data. The allowlist in `swe_structural_policy.json` is only a demo carrier and is **not a safe runtime authorization policy**. The `--expected` label is manually provided and not a verified benchmark judgment.

Validation rejects missing/malformed JSON arguments, ambiguous non-assistant calls, unsupported tool-call envelopes, empty traces and excessive lengths. Both existing schema 1.0 and opt-in 1.1 policies work, but the importer never manufactures user-grant evidence. Real argument values can be sensitive; `artifacts/` is ignored by Git. **No raw public-dataset conversations should be committed without careful rights and privacy review.**

Provenance research: [NVIDIA Open-SWE-Traces source audit](docs/RECORDED_TRACE_SOURCE_AUDIT_20261120.md). A complete **recorded benchmark-run** preview row was imported successfully (48 tool calls, no execution). Its preview bytes and `X-Revision` matched the saved sample and pinned Hub commit. A second, independently retrieved sample of the **relevant identity, role and tool-action columns from revision-pinned source Parquet** reproduced the same ordered 48 tool calls and exact argument objects. This proves *recorded-action interoperability* at that source revision, but **not** byte-level equivalence of the entire conversation row or any real-world authorization accuracy. The importer remains experimental, not a runtime security control.

To recheck provenance when the private, Git-ignored sample is available, run this optional **research-only** script. It fetches metadata and a bounded public preview; it never publishes raw messages, downloads 200+ MB shards or executes recorded actions:

```sh
python scripts/audit_hf_preview_revision.py --local-row artifacts/open_swe_v1_sweagent_firstrow_private.json --revision 4fa4c2ae9afc6b397bc50391d43450c79993c138 --expected-sha256 5dd6520877d2b0b95e6e3bfa39f868d36a3429c821f7d768b200a6ca8edebb40
```

`SERVER_ATTESTED_PREVIEW_MATCH` does **not** claim cryptographic provenance of the preview contents. Unlike the offline evaluator/CLI, this explicitly invoked research script requires internet access; it is not part of the installed package.

For an **independent pinned-Parquet action check**, install optional PyArrow 21 into the already ignored `artifacts/` area and execute the read-only, capped 20 MiB ranged-column audit. It verifies the exact importer-relevant fields, not message content, model reasoning or the full original JSON row. This is for source-repository research, not required for normal package use:

```sh
python -m pip install --target artifacts/rowproof_deps --no-deps pyarrow==21.0.0
# macOS/Linux:
PYTHONPATH=artifacts/rowproof_deps python -m scripts.audit_hf_pinned_parquet_actions --local-row artifacts/open_swe_v1_sweagent_firstrow_private.json
```

On Windows PowerShell, use `$env:PYTHONPATH = (Resolve-Path artifacts/rowproof_deps).Path` before running `python -m scripts.audit_hf_pinned_parquet_actions --local-row artifacts/open_swe_v1_sweagent_firstrow_private.json`. Both research audit scripts are separate from the dependency-free evaluator; neither forwards the raw row, executes recorded tools or generates authorization ground truth.

## Experimental AgentDojo recorded-run import (development main; not in v0.4.0 release wheel)

The stdlib-only `import-agentdojo` command converts a **locally recorded** AgentDojo run into an offline evaluation suite. It extracts assistant function tool calls with object-valued `args`, validates bounded inputs and call IDs, and ignores model prose, tool outputs and the benchmark's utility/security outcome flags when determining authorization. `--expected` must come from independent task review, not the benchmark's success field.

```sh
python -m agent_trace_lab import-agentdojo examples/agentdojo_recorded_synthetic.json --policy-suite examples/agentdojo_policy_simulated_scope.json --case-id synthetic_calendar --expected allow --output artifacts/dojo_synthetic_suite.json
python -m agent_trace_lab evaluate artifacts/dojo_synthetic_suite.json
```

The example is **self-authored synthetic data**. Its scoped allowlist models a simulated calendar-reading task; it is not a real user-grant system. Both importer and evaluator leave recorded actions unexecuted. Output suites may retain sensitive arguments; never commit raw traces without rights review and redaction.

An optional `python -m scripts.audit_agentdojo_import_contrast` research script downloads two *pinned* public AgentDojo run files and two task-definition files, validates SHA-256, and compares a permissive tool allowlist with a calendar-task-only allowlist. In this selected attacked run, the extra `send_email` action passes the permissive policy but is denied by the scoped one. Both runs **abstain** from real-human authorization judgments. This is not a representative attack-detection benchmark.

Counterexample for overrestrictive policies: the opt-in `python -m scripts.audit_agentdojo_email_control` checks a pinned *legitimate* AgentDojo user task requesting an emailed summary and its recorded run. The action targets the task-defined recipient, but a blanket no-send policy denies it. This checks only **simulated tool and recipient scope**, not the correctness of the email content or any genuine human approval. See [the evidence audit](docs/AGENTDOJO_SIMULATED_BOUNDARY.md).

To avoid reporting only cherry-picked cases, the [cross-suite sampling protocol](docs/AGENTDOJO_SAMPLING_PROTOCOL.md) defines an explicitly **non-random**, predeclared source-selection rule and an opt-in `python -m scripts.audit_agentdojo_sampling --check-upstream` audit. It checks four pinned recorded runs from banking and workspace (two no-injection, two injection-attempt exposures) and reports **four simulated-scope abstentions and four human-grant abstentions**. This is a reproducibility/coverage check, **not** a detection-rate benchmark.

The follow-up [preregistered stratified study](docs/AGENTDOJO_STRATIFIED_REVIEW.md) froze its sampling rule in Git commit `3385f7d` **before** reading new results: four suites, two fixed task IDs and three exposure conditions (24 slots). Its bounded `python -m scripts.audit_agentdojo_strata --check-upstream` audit identified **20 available, four missing** recorded runs; the missing Slack `injection_task_0` slots are not replaced. All 24 simulated-scope reviews are **pending/not_reviewed** and all 24 genuine-human authorization labels **abstain**. No external reviewers, trusted grants or detection-accuracy statistics are claimed.

ATL-004H adds a [privacy-minimized review packet and provisional agreement gate](docs/AGENTDOJO_REVIEW_PACKET.md). Its four pinned original task-source files match SHA-256, and the generated packet preserves 24 slots / 20 available / four missing with **48 action names/ordinals only**, excluding prompts, recipients, argument values and publisher result flags. Run `python -m scripts.agentdojo_review_packet --check-upstream` for the optional source audit, or `python -m scripts.agentdojo_review_packet --write-packet docs/agentdojo_review_packet.json` to create a non-overwriting metadata packet. A local `--reviews` input may produce **provisional** agreement counts, but cannot authenticate actual reviewer identities or verify cited source meaning: **zero independent agreement is accepted, and human-grant labels remain abstain**.

An optional source-span provenance auditor (`python -m scripts.agentdojo_span_provenance --digest-span banking L5-L7`, or `--reviews` with a private v2 submission) checks exact cited line bytes against the same pinned task-source SHA. It rejects fabricated or overlapping citations, but **does not** verify reviewer identity, semantic authorization or consent. See the review-packet documentation for limits and inputs.

ATL-004J adds a [source-pinned task-intent feasibility matrix](docs/AGENTDOJO_TASK_SCOPE_FEASIBILITY.md). It summarizes **eight** source-reviewed AgentDojo tasks and preserves the **24 planned / 20 present / four missing** run denominator, without copying prompts, recipients or raw tool arguments. An offline `python -m scripts.audit_agentdojo_task_scope` check and an opt-in `--check-upstream` AST source check verify provenance. **Eleven nonreference tool-name occurrences are only reference-overlap observations, not unauthorized actions or attack detections**; every simulated-action and real-human-grant label remains `abstain`.

ATL-004K adds an opt-in [privacy-limited argument-shape audit](docs/AGENTDOJO_ARGUMENT_SHAPE_AUDIT.md). The `python -m scripts.audit_agentdojo_argument_shapes --check-upstream` command checks 20 SHA-pinned recorded runs and publishes **only safe top-level argument field names and JSON types** for 48 actions (four unsafe field-name occurrences redacted). No actual target, recipient, amount or message content is exposed; neither these shapes nor the benchmark's tool references prove authorization.

ATL-004L adds an [isolated installed-wheel smoke gate](docs/ISOLATED_WHEEL_QA.md), verifying that the experimental `0.5.0.dev0` CLI can import and evaluate synthetic AgentDojo runs outside the checkout. This checks installability and package boundaries, **not** independent authorization accuracy. The source-only research audit scripts are intentionally **not** part of the installed wheel.

## Development wheel determinism (ATL-004M)

An optional [two-build reproducibility audit](docs/DETERMINISTIC_WHEEL_QA.md)
pins SOURCE_DATE_EPOCH to the Git commit timestamp, builds twice and
compares the resulting wheel SHA-256 on the same machine/runner. This checks
repeatability in one environment, not cross-platform binary identity and
not agent-authorization effectiveness.

## Design

An input JSON suite has:

- `schema_version: "1.0"` (legacy) or `"1.1"` (opt-in task grants), one `policy` and an array of labeled `cases`.
- Policy `max_actions` and exact tool allowlist `tools`, each optionally constraining `path_args/allowed_roots` or `url_args/allowed_hosts`.
- Each case has a unique `id`, `expected` label (`allow` or `deny`), and `trace` of `{"tool":"...","arguments":{...}}` events.

See the complete runnable [example](examples/suite.json).

```text
UTF-8 JSON --> strict schema validator --> deterministic event scanner
                       |                     | tool allowlist
                       |                     | POSIX path scope
                       |                     | HTTPS exact-host scope
                       |                     | action budget
                       v                     v
                    exit 2             per-case violations
                                             |
                                             v
                              confusion matrix / report (exit 0/1)
```

The engine returns TP, TN, FP, FN (positive class is `deny`), accuracy, deny precision and recall; ratios without a denominator are `null`. Violations expose code, event index, tool name and optional argument name, **not argument values**.

## Boundary rules and threat model

1. Unknown tools and tools exceeding the action budget are denied. An allowed tool **without configured argument restrictions** allows every argument; policy writers must explicitly declare sensitive fields.
2. Path checks are lexical **POSIX** checks: absolute canonical paths within allowed roots, no traversal or Windows separators. Paths are never opened or followed.
3. URL checks require HTTPS, exactly allowlisted hostname, no userinfo and no nonstandard port. No network requests are made.
4. Input JSON is bounded to 2 MiB, 500 cases and 10,000 events; duplicate JSON keys, malformed policy pairs and unknown schema fields fail validation.
5. This project cannot see unrecorded actions or infer attacker intent. An empty trace is classified `allow`, not declared harmless.
6. **Not an enforcement point:** it does not resolve symlinks, mounts, DNS, redirects, encoded runtime arguments, tool-side effects or delegated authorization. An action flagged by this tool is not proof that an attack succeeded; adapters must still enforce security controls.
7. No telemetry is collected. If evaluating real traces, scrub sensitive data before publishing. Do not infer real-world robustness from only the supplied synthetic fixtures.

The small, inspectable engine complements mature evaluation systems, rather than duplicating them. See [research and alternatives](RESEARCH.md).

## Structure and quality

`agent_trace_lab/schema.py` validates input, `engine.py` evaluates events without side effects, `otlp.py` imports OpenTelemetry JSON spans, `swe.py` experimentally imports offline SWE-style rows, `agentdojo.py` imports recorded AgentDojo tool calls (development main), and `cli.py` produces machine-readable reports. `tests` uses standard-library unittest. CI targets Windows/Linux, Python 3.10 and 3.12.

```sh
python -m unittest discover -s tests -v
python -m compileall -q agent_trace_lab scripts tests
```

See [backlog / checkpoint](docs/BACKLOG.md). Original code and self-authored fixtures are MIT-licensed. The adapted AgentDrift data records are separately CC BY 4.0 licensed with attribution in the external case study.
