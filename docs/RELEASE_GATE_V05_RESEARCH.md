# ATL-004T — development v0.5 research package release gate

**Decision at source checkpoint 136989c (2026-11-21): HOLD for a
qualified portfolio release or production security claim.**
The inspected code is the Python offline research prototype, not a
runtime authorization service, sandbox, or prompt-injection detector.
This matrix is a release-preflight evidence record, not a claim that
v0.5 has been tagged or published.

## Evidence matrix

| Gate | Grounded evidence | Result / consequence |
| --- | --- | --- |
| Owning repo and clean baseline | KIRAA / KPC Core, C:\Projects\kira-agent-trace-lab, main 136989c; no existing KPC project state/registration; source tests 245 discovered, one Windows symlink integration skip | **PASS baseline**; do not create KPC governance state |
| Runnable offline CLI | agent_trace_lab/cli.py implements evaluate, import-otlp, import-swe and development import-agentdojo; recorded actions are never executed; CLI exit codes 0/1/2 | **PASS for documented supported input envelopes**; no runtime enforcement |
| Reproducible dependency-light install | pyproject.toml declares Python >=3.10, no runtime deps, setuptools build; scripts/verify_installed_wheel.py isolates the installed target and runs outside-source synthetic CLI, entrypoint and privacy probes | **PASS local**, plus Windows/Ubuntu Python 3.10/3.12 CI required on the changed commit; no PyPI release |
| Distribution metadata/source links | Inspected pre-fix wheel: correct MIT license, console entrypoint and version, but **Project-URL absent**. ATL-004T adds Homepage/Repository/Issues/Documentation to pyproject.toml and validates actual wheel METADATA, MIT license text, Python range, absent runtime dependencies, platform tag and CLI entrypoint against the source version | **FIX IMPLEMENTED**; separate negative tests, installed-wheel smoke and PR CI gate |
| Source archive rights/privacy boundary | ATL-004U found that the default sdist included 22 test files while omitting their JSON fixtures and referenced research docs. New MANIFEST.in excludes incomplete tests and research-only data from the MIT-only sdist; archive verifier checks source-content equivalence allowing only Git LF/CRLF checkout differences, licensing/metadata, unsafe tar entries and absence of private/adapted cases | **FIX IMPLEMENTED**; sdist-to-wheel build/installed smoke and CI gate, with ATL-004V cross-checkout regression |
| Source data and license separation | LICENSE is MIT and embedded in the distributable. The two adapted AgentDrift examples are separately attributed CC BY 4.0 in docs/EXTERNAL_CASE_STUDY.md; raw NVIDIA/AgentDojo traces are not shipped in the wheel | **PASS scoped distribution rights review**; individual upstream trace rights still apply to any later redistribution |
| README, changelog, reproducible examples | README has setup, architecture, threat model and explicit limits; CHANGELOG records unreleased development behavior; examples and docs/POLICY_CONTRAST_DEMO.md demonstrate self-authored fixtures, including deliberate mismatch | **PASS as research documentation**, not evidence of security effectiveness |
| Technical privacy/data handling | Real imported trace argument values can contain secrets, names and personal data. Private runs belong in Git-ignored artifacts; wheel excludes scripts/docs/examples; input diagnostics suppress identified untrusted key disclosure; import file writes are exclusive/failure-atomic | **PARTIAL**; not a general PII scrubber, nor robust against arbitrary hostile filesystem races |
| Authentic external tool-action interoperability | docs/RECORDED_TRACE_SOURCE_AUDIT_20261120.md records 48 pinned NVIDIA tool-call actions; AgentDojo task/runs source-pinned with 20 of 24 planned exposure files available | **PASS narrowly for selected recorded-action formats**; not full conversation equivalence or representative testing |
| Independently authenticated permission labels | docs/AGENTDOJO_REVIEW_PACKET.md retains 24 human-grant abstentions; authentic user grants and two independent authenticated reviewers absent | **BLOCKED (ATL-004/005)** |
| Generalizable authorization/detection evaluation | No representative, independently ground-truthed safety corpus; synthetic fixture matches are not precision/recall of an attack detector | **BLOCKED (ATL-006)** |
| Product showcase/release | Stable GitHub release v0.4.0 verified previously; current pyproject version is **0.5.0.dev0**, which is development and was not published as a stable 0.5 release; no qualified KiraShop integration | **HOLD (ATL-007)**; no release tag, deploy, or performance claims authorized by this audit |

## Repeatable bounded checks

Run from the repository root:

    python -m unittest discover -s tests -q
    python -m compileall -q agent_trace_lab scripts tests
    python -m pip wheel --no-deps --wheel-dir artifacts/qa-v05-wheel .
    python -m scripts.verify_installed_wheel --wheel-dir artifacts/qa-v05-wheel
    python -m scripts.verify_reproducible_wheel

Wheel verification now requires a source-matching version, MIT license
file and expression, correct Python requirement, no runtime dependencies,
correct console entry point and pure-Python tag, and the repository,
homepage, documentation and issues links. It rejects tampered metadata
and malformed packaging before any result can be counted as PASS.
The wheel build itself may download the declared setuptools build
dependency; subsequent isolated wheel installation is offline.
The reproducible-wheel comparison is **same runner/environment only**.

This review is a **self-review**, not independent security validation
or independent acceptance. GitHub CI is independent execution in
other operating-system/Python environments, not a human code review.

## Release policy

The code may eventually be **published as an explicitly limited research
prerelease** after packaging and release notes are verified, with a
separate version/tag and an unambiguous disclaimer. That would **not**
close ATL-004/005/006/007 or qualify a production/security showcase.
Do not silently promote the development version to stable, advertise
synthetic accuracy as protection, or add the project to kirashop.id.vn
under an unearned claim. Preserve the pending evidence gates.
