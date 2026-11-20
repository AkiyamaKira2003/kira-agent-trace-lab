# v0.5.0.dev1 — Offline Agent Trace Lab research prerelease

**Research-only development prerelease candidate. Not stable v0.5.0 or a security product.**
This stdlib-only Python program evaluates **previously recorded** AI-agent
tool calls against explicit caller-supplied policy. It never executes
recorded calls, contacts a model, authenticates human approvals or
enforces a live agent's permissions.

## Changes since published research prerelease v0.5.0.dev0

- **Five import commands covering four recorded-format families.**
  The new import-responses-sequence accepts a bounded *application-authored*
  local ordered JSON array of completed Responses API objects. This is
  **not a native OpenAI batch endpoint envelope**. The previous
  import-responses single-response, OpenTelemetry, SWE and AgentDojo
  importers remain. Duplicate response/call IDs, incorrect explicit
  previous-response links, unfinished or unsupported hosted calls,
  invalid JSON and oversized input fail closed. Input order/links
  are not independently authenticated history or consent.
- **Safer report publication.** evaluate --output no longer silently
  destroys existing reports; compare-policies --output now saves
  JSON/text with the same complete atomic no-clobber behavior.
  Both support explicit --overwrite, preserve their source files,
  and maintain existing decision and exit-code semantics.
- **Opt-in aggregate-only reports.** evaluate --summary-only for JSON
  or text omits individual case IDs, tool names, arguments and
  violations. The counts are from **caller-supplied fixture labels**;
  this is not real-world authorization accuracy, precision or recall.
  compare-policies --redact-case-ids also works for saved reports.
- **Bounded failure diagnostics.** Filesystem and JSON/UTF-8 parsing
  failures no longer echo raw private path-rich exception text.
  This is not whole-trace anonymization; normal inputs and detailed
  reports may still contain private identifiers and arguments.
- **Verification.** Actual installed wheel console/module behavior
  across all five import commands, MIT-only source archive, wheel
  rebuilt from source archive, same-runner reproducible wheel builds
  and Windows/Ubuntu Python 3.10/3.12 GitHub CI.

## Installation and self-authored examples

Only after the GitHub release is actually published, download the
v0.5.0.dev1 wheel attached to that **research-only prerelease**
and compare its SHA-256 against the attached SHA256SUMS.txt:

    python -m pip install ./kira_agent_trace_lab-0.5.0.dev1-py3-none-any.whl
    agent-trace-lab --help

Python 3.10+ is required, with no third-party runtime dependencies.
There is **no PyPI distribution**. To execute the self-authored
fictional examples, clone the tagged Git repository:

    python -m agent_trace_lab evaluate examples/suite.json --summary-only --format json
    python -m agent_trace_lab import-responses-sequence examples/responses_sequence_synthetic.json --policy-suite examples/suite.json --case-id research_demo --expected allow --output artifacts/demo_sequence.json
    python -m agent_trace_lab compare-policies examples/demo_permissive.json --candidate-policy examples/compare_candidate_task_guarded.json --redact-case-ids --format json --output artifacts/policy_delta.json
    python -m unittest discover -s tests -q

Import only validates recorded function names/arguments and preserves
their declared order; it **does not execute tools**. Expected labels
are supplied by the operator, not derived from authenticated user
consent. Synthetic 8/8 fixture agreement is regression conformance,
not an attack-detection result.

## Release artifacts, licensing and explicit nonclaims

The research gate requires the Python wheel, MIT-only installable
source tar.gz and SHA256SUMS.txt containing digests of the actual two
assets. Check the exact downloaded bytes against the manifest.
SHA-256 establishes integrity, **not publisher authenticity**.
Same-runner byte reproducibility is not cross-platform identity.

The packaged wheel and source archive exclude tests, examples,
research scripts, private/raw traces and separately attributed
CC BY 4.0 adapted AgentDrift examples in the Git repository.
No redistribution rights to external raw trace datasets are implied.

**The following remain unverified and on HOLD:**

- No live-agent sandbox, authorization gateway, runtime enforcement
  or prompt-injection detector.
- No independently authenticated user/task/grant records or two
  independently authenticated external reviewers. Genuine
  user-grant labels remain abstain.
- No representative externally established authorization/safety
  ground truth, valid real-world detection precision/recall or
  generalizable protection statistics.
- The frozen AgentDojo exposure inventory still has 24 intended
  slots, 20 available and four missing; benchmark outcomes
  cannot substitute for authenticated approval.
- Raw trace arguments may include PII, credentials, file paths
  and recipients. Privacy modes do **not** anonymize arbitrary
  original files or all output.
- No certified security product, stable v0.5 release, PyPI claim
  or qualified production KiraShop security showcase.

Passing a packaging/CI release gate authorizes **only a research-only
GitHub prerelease**. The project remains ACTIVE with independent
human authorization, external evaluation and qualified showcase HOLD.
