# ATL-004P — No untrusted JSON keys in validation diagnostics

The offline CLI accepts recorded trace data that is **untrusted**. An input
can contain private-looking material not only as JSON values, but also in
object property names or tool identifiers. In the prior version, validation
errors could echo those names to stderr:

- Duplicate JSON property errors printed the duplicated key.
- Unexpected schema properties were printed as a list of actual keys.
- Invalid tool names and tool-validation locations repeated the supplied
  tool name.

The issue was reproduced locally using only synthetic secret-like markers,
not real credentials or user data.

## Current behavior

- Duplicate JSON properties are still rejected but no longer include the
  untrusted property name.
- Unexpected properties are still rejected with their **count** and
  the trusted schema location. Names of **missing required fields** are
  preserved because they are defined by the application schema itself.
- Tool validation errors refer to `policy.tools[index]`, a bounded numeric
  position, instead of printing user-supplied tool names.
- This changes error-message wording only. Strict schema checks, the
  offline trace evaluator, importer behavior and CLI exit semantics remain.

Reproduce:

```sh
python -m unittest tests.test_diagnostic_redaction -v
python -m unittest discover -s tests -q
```

The eight new tests confirm that a synthetic untrusted key never appears
in exceptions, CLI stderr or the installed wheel's malformed-input
diagnostics. Both the installed console launcher and the installed
`python -m` module must reject the intentionally malformed fixture with
exit 2 without leaking the synthetic key. Ordinary valid suites still pass.

**Boundary:** This is limited to the identified JSON validation error
paths, **not a general PII scrubber**. Normal reports intentionally show
tool names and case identifiers from traces, and imported private JSON
can contain raw argument values. Do not publish unreviewed real-world
traces, CLI reports or build logs as if they were anonymized. The tool
continues to be a static research evaluator, not an authorization server.
