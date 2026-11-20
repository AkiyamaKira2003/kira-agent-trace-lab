# ATL-004L — Isolated development wheel reproducibility gate

**Scope:** verify that the **0.5.0.dev0** package actually contains the
stdlib-only offline evaluator/importers and works once installed, outside its
source checkout. This is a release-readiness smoke test, **not** a stable
release, a security certification or an AI-agent performance benchmark.

## Reproduction on Windows, Linux or macOS

From the existing source repository, with Python 3.10+ and its declared
`setuptools>=68` build backend already installed:

```sh
python -m pip wheel --no-deps --no-build-isolation --wheel-dir artifacts/qa-wheel .
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
all machines is not asserted by this check. The build backend must be
available locally; `--no-build-isolation` avoids downloading dependencies
for the build command, while installed runtime smoke uses `--no-index`.
