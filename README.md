# Kira Agent Trace Lab

**Offline, deterministic evaluation of tool-using AI-agent traces.** This Python prototype evaluates recorded tool calls against an explicit allowlist policy. It never executes those calls or invokes a model.

> This is a research prototype, not a sandbox, runtime authorization mechanism, prompt-injection detector or proof of an agent's security.

## Quick start

Python 3.10+, no runtime dependencies, network access or model API keys required:

```sh
python -m agent_trace_lab evaluate examples/suite.json
python -m agent_trace_lab evaluate examples/suite.json --format json
python -m agent_trace_lab evaluate examples/suite.json --format json --output artifacts/report.json
python -m unittest discover -s tests -v
```

Exit **0** means all expected case labels matched, **1** means at least one mismatch, and **2** means invalid input/I/O failure. The same input yields the same report.

The included synthetic example yields **8/8 labeled matches** with TP=5 and TN=3. **This is a smoke test, not an independently measured agent-safety score.**

## Design

An input JSON suite has:

- `schema_version: "1.0"`, one `policy` and an array of labeled `cases`.
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

`agent_trace_lab/schema.py` validates input, `engine.py` evaluates events without side effects, `cli.py` produces machine-readable reports. `tests` uses standard-library unittest. CI targets Windows/Linux, Python 3.10 and 3.12.

```sh
python -m unittest discover -s tests -v
python -m compileall -q agent_trace_lab tests
```

See [backlog / checkpoint](docs/BACKLOG.md). Original code and fixtures are MIT-licensed; researched third-party projects retain their own licenses.
