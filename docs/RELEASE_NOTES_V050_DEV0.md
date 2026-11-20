# v0.5.0.dev0 — offline agent trace evaluation research prerelease

**Research-only development prerelease. Not a stable v0.5.0 or a security product.**
This is a stdlib-only, offline evaluator of **already recorded**
AI-agent tool calls against an explicit user-supplied policy. It never
executes recorded tools or contacts a model. It does not provide
runtime enforcement, authenticated approvals or detection of
unobserved agent actions.

## What is new since stable v0.4.0

- **Four narrowly supported recorded-action formats:** OpenTelemetry
  OTLP/HTTP JSON execute-tool spans, SWE-style assistant tool-call rows,
  AgentDojo saved runs, and a single completed OpenAI Responses API
  output object with function calls. Parsers are bounded and strictly
  validated; they do not claim arbitrary stream or SDK compatibility.
- **Safer import writes:** existing outputs are not silently
  overwritten (explicit --overwrite is required). First-time output
  is published only after writing the complete JSON. This is tested
  local file behavior, not a proof against hostile filesystem races.
- **Compare policies on the exact same recorded cases:** compare-policies
  accepts a baseline suite and a policy-only candidate, reporting
  decision transitions without inventing human authorization labels.
  Opt-in --redact-case-ids substitutes per-report ordinal case aliases;
  this is not universal anonymization or private-trace scrubbing.
- **Expanded QA:** isolated wheel install, actual console launcher/module
  parity, same-environment source-date-pinned wheel reproducibility,
  minimal MIT-only sdist, wheel rebuilt from the sdist, and CI for
  Ubuntu/Windows Python 3.10/3.12.

## Installation and reproducible examples

Download the research prerelease wheel attached to GitHub tag
**v0.5.0.dev0**, then run locally:

    python -m pip install ./kira_agent_trace_lab-0.5.0.dev0-py3-none-any.whl
    agent-trace-lab --help

Alternatively install the source distribution as a code-only package.
Python 3.10+ is required; runtime dependencies are empty. This is
**not** published to PyPI. The installable archives deliberately do
not include the tests, synthetic examples and research-only tools.
Clone the Git repository to run those reproducible demonstrations:

    python -m agent_trace_lab evaluate examples/suite.json
    python -m agent_trace_lab import-responses examples/responses_function_calls_synthetic.json --policy-suite examples/suite.json --case-id demo --expected allow --output artifacts/response_demo.json
    python -m agent_trace_lab compare-policies examples/demo_permissive.json --candidate-policy examples/compare_candidate_task_guarded.json --format json --redact-case-ids
    python -m unittest discover -s tests -q

Importing only converts recorded function call data; it **does not**
execute any tool. Expected labels are supplied by the caller, not
derived from authenticated user consent. Normal evaluation scores on
synthetic examples are fixture checks, not empirical agent safety
statistics.

## Artifacts, verification and license limits

The release must include the pure-Python wheel, the MIT-only installable
source .tar.gz and SHA256SUMS.txt recording checksums of those exact
two attached artifacts. Compare file digests after download.
Same-runner reproducibility does **not** imply byte-for-byte identity
between machines or independently attest the release publisher.

Distributable files exclude source-only research scripts, docs, tests,
examples, private artifacts and external datasets. Original package
source and self-authored fixtures are MIT; the source repository also
contains separately attributed **CC BY 4.0** adapted AgentDrift
examples. Those examples are **not** included in the MIT-only wheel
or sdist. No right to redistribute original third-party raw traces
is implied.

## Explicit nonclaims and outstanding gates

- No runtime sandbox, authorization gateway, prompt-injection detector,
  model call or real agent-tool action execution.
- No independently authenticated human grant/task pairs or two genuine
  independent authenticated external reviewers. Genuine user-grant
  labels remain **abstain**.
- No representative, independently established safety test population.
  No real-world detection precision, recall or authorization accuracy.
- The preregistered AgentDojo study has **24 intended exposures**:
  20 available and 4 missing. Task-source metadata and selected tool
  calls do not prove consent.
- Imported arguments may contain personal data, recipients, prompts
  or credentials. Output and error paths are **not universally
  anonymized**; never publish private recorded data without review.
- No production-security endorsement, certification or qualified
  KiraShop security integration.

Release packaging success and GitHub CI are engineering evidence only.
The project remains **ACTIVE** with its real-user approval, independent
evaluation and qualified showcase gates **HOLD**.
