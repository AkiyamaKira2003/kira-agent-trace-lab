# ATL-004L — Isolated development wheel reproducibility gate

**Scope:** verify that the **0.5.0.dev0** package actually contains the
stdlib-only offline evaluator/importers and works once installed, outside its
source checkout. This is a release-readiness smoke test, **not** a stable
release, a security certification or an AI-agent performance benchmark.

## Reproduction on Windows, Linux or macOS

From the existing source repository, with Python 3.10+:

```sh
python -m pip wheel --no-deps --wheel-dir artifacts/qa-wheel .
python -m scripts.verify_installed_wheel --wheel-dir artifacts/qa-wheel
python -m unittest discover -s tests -q
```

The verifier requires exactly one locally built wheel in the requested
directory. It checks the archive for package CLI/importer components and
refuses an archive containing research-only `scripts/`, `docs/`, raw
`artifacts/`, `examples/` or `.env` files. This is a packaging
sanity check, **not** a sandbox for untrusted wheels.

It installs the wheel into a temporary, ignored `artifacts/` location
using `pip install --no-index --no-deps --target`, starts a second Python
process with `-S` and `PYTHONPATH` pointing **only** to that installation,
and checks that the imported package really comes from that target path.
The work directory contains just **self-authored synthetic** fixture copies,
not the repository package source.

The installed CLI then:

1. Runs `import-agentdojo` on the synthetic two-tool-call example,
   with an explicitly **caller-provided** expected label. No tool call is
   executed; conversion writes only a temporary JSON fixture.
2. Re-evaluates that imported suite (1/1 fixture label match).
3. Evaluates the existing eight-case synthetic suite (8/8 fixture
   label matches).
4. Removes all temporary site-install and fixture files automatically.

ATL-004O also checks the **actual installed console entrypoint**
`agent-trace-lab`: with `pip --target`, launcher files live under the
target `bin/` directory on both Windows and POSIX systems (Windows uses
`agent-trace-lab.exe`). The verifier checks that the launcher is present
inside the installed target, is executable on POSIX, and produces exactly
the same parsed JSON and exit codes as `python -S -m agent_trace_lab` for
both the deliberately mismatched permissive demo (exit 1) and five-case
task-scoped demo (exit 0). This check runs in the same outside-source,
temporary environment and does not invoke a model or replay actual tools.

The result contains the built wheel SHA-256, package-member count and
verified synthetic fixture counts, **not raw trace arguments**. There is
no claim of independent authorization, genuine human grants, production
readiness or model attack-detection accuracy.

## CI gate and package boundaries

The [test workflow](../.github/workflows/test.yml) runs this build and
isolated-install check on **Ubuntu and Windows**, each with **Python 3.10
and 3.12**, after unit tests and local CLI smoke tests.

The installed package intentionally contains only `agent_trace_lab`
runtime modules. Upstream-source provenance and metadata auditors under
`scripts/` remain **research-only source-checkout tools**, not installed
console commands. The existing stable v0.4.0 release is unchanged;
`0.5.0.dev0` is a development wheel built from this checkout and has
not been published as a stable release by this task.

Wheel build reproducibility at the **byte-identical** level across
all machines is not asserted by this check. During **wheel construction**,
pip's isolated PEP 517 build environment may download the declared
`setuptools>=68` backend. This avoids depending on stale or missing
preinstalled build tools (observed on Windows Python 3.10 and Python 3.12
runners). `--no-deps` disables runtime dependency resolution, while
the **installed-wheel smoke itself** uses `--no-index --no-deps` and
does not fetch dependencies. An intentionally offline *build* is possible
using `--no-build-isolation` only after independently installing a
compatible build backend.
