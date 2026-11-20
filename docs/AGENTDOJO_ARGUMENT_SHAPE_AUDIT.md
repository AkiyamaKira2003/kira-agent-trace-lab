# ATL-004K — Privacy-limited recorded argument key/type inventory

This research step extends the [pinned task-intent matrix](AGENTDOJO_TASK_SCOPE_FEASIBILITY.md)
and the fixed [24-slot AgentDojo study](AGENTDOJO_STRATIFIED_REVIEW.md).
It is **not** a source of user permission or a prompt-injection detection score.

## What was actually verified

- **20/20 available** runs in the already preregistered 24-slot sample were
  fetched at the immutable AgentDojo commit
  `089ed468cf3ed0322acc66b0211f26d9d90dbf60` and matched their
  existing SHA-256 hashes and ordered recorded tool names.
- The **four original missing Slack slots** remain explicitly missing,
  not zero-action events or artificially replaced attack scenarios.
- Exactly **48 recorded actions** were inventoried. Only allowlisted,
  generic API **argument field names** and coarse JSON **types** are stored.
  Four top-level field-name occurrences not in the review-safe allowlist
  are replaced with `unlisted_name`; the original names are never published.
- **No argument values** are retained: no message bodies, hotel identities,
  addresses, recipients, bank accounts, payment amounts, URLs or nested data.
  A nested array or object is recorded simply as `array` or `object`.
  The publisher's `utility` and `security` outcome flags are omitted.
- All **24 simulated-scope and real-human authorization judgments remain
  `abstain`**, with zero independent reviewers and zero accepted grant labels.

The machine-readable
[argument shape manifest](agentdojo_argument_shapes.json) holds source paths
and hashes, stable action IDs, previously observed tool names and
`{name,type}` pairs only.

## Reproducibility

```sh
python -m scripts.audit_agentdojo_argument_shapes
python -m scripts.audit_agentdojo_argument_shapes --check-upstream
python -m unittest discover -s tests -q
```

Offline is the default; it checks the committed inventory's size,
schema, missingness, action IDs, source-hash linkage, safe field names and
required abstentions. It does **not** independently prove the submitted type
shapes against source bytes. The optional network mode reads the same
source-pinned **20** runs, bounded to **64 KiB each** and at most **1.5 MiB**
of public source payloads in total; it independently recomputes the redacted
shapes and requires byte-for-byte metadata equality. A
`--capture-upstream` command is for first-time metadata generation only and
fails if an inventory already exists.

The verifier parses JSON in memory; it does not execute recorded tools, call
any agent, import upstream code or publish source conversations. Errors omit
untrusted text. Unit tests include deliberately private-looking synthetic
argument keys, secret-bearing nested objects, altered SHA-256, missing slots
and fabricated permissions.

## Trust boundary and next step

Type and field-name equality **cannot establish** whether any specific
recipient, amount, hotel or calendar date was authorized. Even a recorded
tool name matching the benchmark's reference implementation is insufficient
to verify its arguments or causal timing. A human authorization ground truth
still requires authenticated principals, original task context, trusted
grant issuance and independent review. No precision/recall or success rates
are computed from this inventory.

For a future narrow source-backed comparison, inspect only necessary target
fields in a privacy-safe offline environment and keep all remaining judgments
`abstain` until there is sufficient source provenance and review evidence.
