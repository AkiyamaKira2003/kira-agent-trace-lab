# ATL-004H — Source-pinned, privacy-minimized review packet

**Scope:** metadata-only, *simulated-task* annotation preparation for the [preregistered 24 AgentDojo exposures](AGENTDOJO_STRATIFIED_REVIEW.md). Neither this procedure nor its output verifies actual human authorization, proves an agent attack occurred, or produces representative safety accuracy metrics.

## Source and rights review (2026-11-21, Asia/Ho_Chi_Minh)

- Original publisher: [ETH Zurich SPY Lab / AgentDojo](https://github.com/ethz-spylab/agentdojo), repository MIT license; use with attribution. Exact recorded-run and task-code revision: `089ed468cf3ed0322acc66b0211f26d9d90dbf60`.
- Four original task source files at `src/agentdojo/default_suites/v1/{banking,slack,travel,workspace}/user_tasks.py` were downloaded read-only **at the pinned revision**, checked against SHA-256 and confirmed to contain `UserTask0` and `UserTask1`. Exact hashes and sizes are recorded in [agentdojo_task_sources.json](agentdojo_task_sources.json); nothing was imported or executed.
- The original task **code** is independent of the observed agent calls. Merely identifying a class, however, does **not** independently extract/verify its full task wording, recipient constraints, authorized arguments or each logged action's causal relation to the request.
- Prior frozen exposures remain **24 intended / 20 present / four absent** (all missing in Slack injection task 0). The 20 runs have **48 tool-call occurrences**. The same missing entries remain missing; no replacement or guessed action count.
- Recorded conversations can contain email addresses, banking account identifiers, untrusted instructions and other sensitive arguments. The committed packet includes **none** of the raw task prompts, tool arguments, recipient values, messages, publisher utility/security results or generated content. Only source paths, hashes, source URLs, tool names and action ordinals are included.

## Reproducible packet creation

```sh
python -m scripts.agentdojo_review_packet
python -m scripts.agentdojo_review_packet --check-upstream
python -m scripts.agentdojo_review_packet --write-packet docs/agentdojo_review_packet.json
python -m unittest discover -s tests -q
```

`--check-upstream` opts into four bounded read-only HTTPS requests (128 KiB + one byte per task-source file, no code execution) and fails if size, SHA-256 or task class differs. Default execution is strictly offline. `--write-packet` uses exclusive creation; it will **not overwrite** previous evidence. Packet generation uses the previously validated, Git-preregistered manifest and preserves all 24 source slots. No recorded action is executed.

## Independent human review requirements (not yet satisfied)

1. A trusted coordinator independently authenticates **two different actual human reviewers** and protects evidence of who reviewed which packet. An unverified `reviewer_id`, an arbitrary URI or a self-asserted statement is **not** identity authentication.
2. Each reviewer independently reads the *original task definition* from the pinned code and privately inspects only the necessary argument scope in the corresponding immutable recorded run. Never copy raw sensitive fields into public JSON or use a model's response as the grant source. Reviewer instructions must not include publisher utility/security verdicts or the other person's label.
3. For each action, the reviewer may assign `within_scope`, `out_of_scope` or `abstain` **relative to the simulated legitimate task only**, with the exact pinned task-source SHA, source line reference (`L20-L30` form), and a rationale without PII. If the tool name does not reveal the target/recipient/action contents, **abstain** until it can be verified privately.
4. Two independent responses form a candidate pair only if they refer to the same immutable `action_id`. Conflicting responses require a genuinely independent adjudication process; absent/missing actions never become negative cases. Keep genuine human-grant labels `abstain` throughout.
5. The offline calculator only checks **submission structure** and computes **provisional** coverage, agreement, abstentions and disagreement counts. It cannot verify actual reviewers' identities, task-source span semantics, independent/blind process, or consent provenance. Thus `accepted_independent_agreements` stays **zero** even if two strings agree. An external trusted verification and adjudication workflow is a separate release gate.

Example **shape only**, using fictional identifiers and **no** completed review claims:

```json
{
  "schema_version": "agentdojo-blinded-review-submission-1",
  "reviewers": [
    {"reviewer_id": "person_one", "identity_evidence_ref": "private-review-register-A"},
    {"reviewer_id": "person_two", "identity_evidence_ref": "private-review-register-B"}
  ],
  "reviews": []
}
```

To check an actual local file (keep it Git-ignored, e.g. `artifacts/reviews_private.json`), run:

```sh
python -m scripts.agentdojo_review_packet --reviews artifacts/reviews_private.json
```

The returned result is deliberately tagged `PROVISIONAL_ONLY_IDENTITY_AND_SOURCE_CITATIONS_NOT_INDEPENDENTLY_VERIFIED`. It never emits reviewer names, source excerpts, private arguments or review rationales. Failed validation returns a generic error type, not sensitive content.

## Remaining gates

**Source-hash checks and packet generation are verified. Actual blinded reviews, reviewer identity evidence, source-span semantics and independent adjudication are not verified.** No grant-level safety rates, precision/recall, or KiraShop portfolio showcase should be published from these packets. Next bounded task: design an authenticated external reviewer/attestation and privacy review workflow, then recruit genuinely distinct reviewers only with consent and sufficient source access.
