# ATL-004AA — explicit research-only prerelease GO/NO-GO

**Reviewed:** 2026-11-21 (Asia/Ho_Chi_Minh).
**Owning machine:** KIRAA / KPC Core.
**Repository:** C:\Projects\kira-agent-trace-lab.
**Initial clean source checkpoint:** 43513e163e5937a942ce514086c2551845cbdaba.

This is a bounded **self-review**, not an independent human security
audit. The source-checkpoint GitHub Actions run
[44812513495](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/actions/runs/44812513495)
passed all four Ubuntu/Windows Python 3.10/3.12 jobs. The final
release tag must be separately checked against the final merged
revision and a fresh successful CI run.

| Preflight requirement | Observed basis | Decision |
| --- | --- | --- |
| Owning repository, revision and clean source | KIRAA, KPC Core, public MIT repository, clean synchronized main at baseline; no project.state.json | PASS |
| Existing release/version | Stable v0.4.0 has published wheel and SHA256SUMS; 0.5.0.dev0 is the pyproject PEP 440 development version, without a previously published tag | PASS for separate prerelease only |
| Open issues and review | Issue #14 remains open for independently sourced authorization labels; no open PR at baseline | DISCLOSED, not an accepted independent review |
| Runnable CLI | Deterministic offline evaluator; four recorded-input adapters, exact-case comparison and optional case-ID aliases; Python 3.10+, zero runtime dependencies | PASS for supported formats, not runtime safety |
| Regression verification | 288 tests discovered on KIRAA, 287 PASS and one Windows symlink-privilege skip; CI run above 4/4 success | PASS scoped engineering |
| Package bounds and licensing | MIT LICENSE; package metadata with project links; MANIFEST.in excludes adapted CC BY 4.0 data, tests, docs, scripts and private artifacts; source verifier and isolated installed-wheel smoke available | PASS for original-code distributions; no third-party trace-redistribution claim |
| Packaging repeatability | Source-date-pinned wheel comparison identical within each runner; source-to-sdist-to-wheel installed smoke in CI | PASS within environment, not cross-OS byte identity |
| README, architecture, real examples and limitations | README, changelog, original synthetic demonstrations, pinned research evidence and [notes for this limited release](RELEASE_NOTES_V050_DEV0.md) | PASS for research disclosure |
| Authenticated user grants and reviewers | No trusted real-user authorization ledger, no two independently authenticated reviewers; all real-grant labels abstain | NO-GO security-product qualification |
| Representative security performance | No externally representative, independent user-action truth set, no defensible real-world precision/recall | NO-GO detection or efficacy claims |
| Public portfolio security showcase | No qualified product-grade evaluation, KiraShop deployment intentionally not attempted | HOLD (ATL-007) |

## Conditional publication decision

**GO only for an explicitly labeled research-only GitHub prerelease**
using the package version and tag **v0.5.0.dev0**, conditional on:

1. The final merged revision is clean, pushed, and the corresponding
   Windows/Ubuntu Python 3.10/3.12 CI jobs all PASS.
2. Two real release files are produced from precisely the tag commit:
   a wheel and MIT-only sdist with correct package version, metadata,
   entrypoint, license and no private/raw external trace records.
3. The real wheel and a wheel rebuilt from the sdist pass the existing
   outside-checkout installed-module/console tests, source inventory
   and within-runner deterministic build check.
4. Actual SHA-256 checksums are written for those *exact* uploaded
   assets, never copied from an older build.
5. Release notes prohibit claims of runtime enforcement, human
   authorization accuracy, independent evaluation or a production
   KiraShop security integration.
6. GitHub marks v0.5.0.dev0 as **prerelease**, and the stable
   v0.4.0 remains the latest stable release.

If any gate fails, the release decision becomes **HOLD**, and no
tag/publication should occur. A successful limited prerelease
**does not** close ATL-004/005/006/007 and never makes the whole
project VERIFIED COMPLETE.

The final source SHA, release assets/digests, published release URL
and any blockers belong in the existing canonical docs/BACKLOG.md
checkpoint, never in a duplicate campaign state file.

## Published research-only prerelease readback — ATL-004AB

The conditional preflight was fulfilled for the exact tagged source
commit **e590a177aaa0faafb9493181b3b62c9e989cf571**, with
[final merged-main CI 44813557201](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/actions/runs/44813557201)
**4/4 PASS**. An annotated remote tag v0.5.0.dev0 peels to that
commit. The release is visible at
[v0.5.0.dev0](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.5.0.dev0):
**draft=false, prerelease=true**. GitHub's latest-stable endpoint
continues to return **v0.4.0**.

| Uploaded asset | Bytes | SHA-256 verified against GitHub and download |
| --- | ---: | --- |
| kira_agent_trace_lab-0.5.0.dev0-py3-none-any.whl | 29184 | 4a831b863f634842e285ac38bdd738de44e626e64224f3a3b61c8aaf5d94bd71 |
| kira_agent_trace_lab-0.5.0.dev0.tar.gz | 35362 | 51b4fb23fb1fddec7b02c725ec194da3c1dfe6b8c542c08a0623b3c81c961daa |
| SHA256SUMS.txt | 220 | 1c482a7a929eaf76d653811f4cca95f15b4fec448f1de5decd88cf395716fd4e |

GitHub draft release bytes were **downloaded again** and compared
byte-for-byte with KIRAA's pinned-tag staging files before publication.
The attached SHA256SUMS.txt also independently rehashed and matched
the downloaded wheel and tar.gz. Source archive inventory, rebuilt
wheel smoke, installed console/module parity across four importers
and within-runner deterministic wheel check all passed for the
tag source. The checksum list is an integrity check, **not** a
cryptographic publisher identity signature.

**Final release decision:** GO executed **only** for a research
prerelease. Qualified product/stable v0.5 release, independently
authenticated grants, external safety effectiveness statistics
and KiraShop security showcase remain **HOLD**.
