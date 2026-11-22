# ATL-004DL — offline declared-batch manifest integrity proof

**Decision (2026-11-22): LOCAL_DECLARED_BATCH_INTEGRITY_PASS / NO_AUTHENTIC_COMPLETENESS / QUALIFIED_SECURITY_RELEASE_HOLD.**

## Scope and explicit nonclaim

The [actual two-POST SDK proof](OTLP_MULTI_POST_COMPLETENESS_20261122.md) showed that one valid OTLP/HTTP JSON request can omit later tool actions. The source-only prototype in scripts/verify_otlp_capture_manifest.py validates a **caller-declared** batch set, rather than creating a trusted recorder. SHA-256 verifies that local bytes match the declaration. It **cannot** authenticate who declared the batch count, prove that there was no unrecorded third POST, infer human consent, or establish production security effectiveness. It is not shipped in the Python runtime wheel.

The manifest object must contain exactly two fields, expected_batch_count (integer 2–8) and batches (same number of ordered entries). Each entry contains exactly index (consecutive integers starting at 1) and sha256 (lowercase hex, 64 characters). Names are **derived** from each validated index: http-post-1.json, http-post-2.json, and so forth. Untrusted manifest data is never used as a file path.

The verifier rejects missing/extra files with the http-post- prefix, duplicate/out-of-order indexes, repeated digests, byte/hash mismatches, malformed JSON, invalid/foreign trace IDs, and replayed span IDs across batches. Each batch is limited to 512 KiB; the set is limited to 2 MiB, 10,000 spans and the existing 100-resource-group importer bound. Existing strict JSON parsing and importer validation are reused. Ignored non-tool spans may omit both IDs, as in existing OTLP fixtures; when IDs exist, they must be valid and share the same trace. The source-only symlink precheck is **not** a race-free filesystem sandbox; use only privately owned local test folders.

## Reproduce the locally controlled synthetic proof

On KIRAA, Node 26.13.0 and Python 3.12.10, the previous task's two original, official JavaScript exporter JSON captures were **copied**, not moved or replaced, into a new Git-ignored folder artifacts/atl004dl_manifest_20261122. A locally generated manifest recorded SHA-256 of the **saved pretty-printed JSON files**, not raw wire POST bodies:

| Local file | Bytes | Saved-file SHA-256 |
| --- | ---: | --- |
| http-post-1.json | 1713 | edbf7fafaf89d8a95acbc66a96914be025a5db36003909b975430371d94f379b |
| http-post-2.json | 2327 | 1ae6a7a6d8743fb960c6bf9b9bb714ec86871c5140e9615e4df876b592f7ce5e |

The new manifest.json SHA-256 was 7d516dd40e561ccfc616dd3c19583a8ff4c894ec353579c143846a4bb529ddd3. Re-run from the repository root with:

~~~powershell
python -m scripts.verify_otlp_capture_manifest --capture-dir artifacts/atl004dl_manifest_20261122 --manifest artifacts/atl004dl_manifest_20261122/manifest.json --policy-suite examples/suite.json --case-id synthetic_two_post --expected deny
python -m unittest tests.test_otlp_capture_manifest -v
~~~

The first command exited 0 with status SELF_DECLARED_LOCAL_BATCH_SET_VALIDATED, declared_batch_count=2, recorded_tool_call_count=2, and explicit false values for end_of_trace_authenticated, user_authorization_authenticated and recorded_actions_executed. The checker prints counts only and writes no imported output file. No external endpoint, actual tool call, owner application, customer data, signing key or remote service is involved.

## Negative tests and remaining HOLD

The isolated unit matrix tests missing/extra files, duplicate/gapped/out-of-order indexes, invalid count/keys, changed file data, malformed digests, duplicate payload hashes, oversized input, mixed trace IDs including parent spans, replayed span IDs, duplicate JSON keys carrying a synthetic private marker and bounded CLI failures. Synthetic fixtures alone are not evidence of user-approved actions.

**NO_AUTHENTIC_COMPLETENESS:** An incomplete capture whose author declares two POSTs can still pass even if the real exporter sent three. A production collector would need a separately authenticated capture owner and end-of-trace/expected-count proof, replay-resistant receipt chain, durable storage and timeout/abort handling. These do not exist here. No tag, release, deployment or qualified KiraShop security showcase is authorized by this proof.
