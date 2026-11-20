# ATL-004AI — evidence-based dev1 prerelease GO/NO-GO

Reviewed 2026-11-21 on KIRAA via KPC Core, in
C:\Projects\kira-agent-trace-lab. This is **self-review only**,
not independent external security validation or human authorization.

| Gate | Checked evidence | Decision |
| --- | --- | --- |
| Repository and ownership | clean pushed main e09a951a12fc2dc4f3495f16c14ac991f6857e50; KIRAA/KPC Core; no valid project.state.json and loaded registration | PASS |
| Existing stable and prior prerelease | GitHub Latest stable v0.4.0; research-only v0.5.0.dev0 already published on immutable annotated tag e590a17; no dev1 tag at baseline | PASS for a separate prerelease |
| Source and runtime | pyproject version 0.5.0.dev1; Python 3.10+, no runtime dependencies, MIT-only distributable code | PASS |
| Changes since dev0 | PRs #42–47 cover development version, safe evaluate reports, aggregate-only reports, local Responses sequences, atomic policy-delta files and private I/O diagnostic redaction | PASS for scoped functionality |
| Regression/package QA | 333 tests discovered: 330 PASS, three Windows symlink-permission SKIPs; installed direct wheel, MIT-only 23-member source archive and sdist-rebuilt wheel smoke PASS | PASS local |
| Cross-platform CI | PR #47 GitHub Actions run 44820112580 passed 4/4 Windows/Ubuntu Python 3.10/3.12; final **tag source commit** CI must additionally PASS | CONDITIONAL |
| Authentic grants and independent reviewers | No independently authenticated human-grant ledger or two independent authenticated external reviewers | **NO-GO production security qualification** |
| Representative external safety accuracy | No independently established representative ground-truth authorization corpus, four archived AgentDojo Slack exposures missing | **NO-GO protection statistics** |
| Qualified portfolio security showcase | No validated security product; no KiraShop deployment | HOLD |

## Conditional publication decision

**GO only for research-only GitHub prerelease v0.5.0.dev1**,
never stable v0.5.0 or a production security claim, after:

1. Final merged clean main revision is pushed and all four GitHub
   Windows/Ubuntu Python 3.10/3.12 jobs PASS on that exact SHA.
2. No existing local or remote dev1 tag/release; annotated new
   tag peels to exactly the final verified source revision.
   Never mutate published dev0 or stable v0.4.0.
3. Build exact-tag wheel and MIT-only source archive, verify metadata
   license and file inventory, installable console/module parity,
   wheel rebuilt from archive and two pinned same-runner deterministic
   wheel builds.
4. Generate fresh SHA256SUMS.txt from those two actual artifacts.
   Upload wheel, archive and manifest to **draft** GitHub prerelease
   with latest=false. Download all three and compare exact bytes
   plus rehash each manifest entry **before publishing**.
5. Read back published GitHub metadata:
   draft=false, prerelease=true, Latest stable still v0.4.0,
   previous dev0 release/tag unchanged. The notes retain every
   explicit nonclaim in RELEASE_NOTES_V050_DEV1.md.

Any failed gate means **HOLD** without release publication.
Research-only publication never closes the missing authentic grants,
independent review, representative safety metrics or qualified
KiraShop showcase. Append the final source SHA, CI run, exact
assets/digests, URL, decision and NEXT_ACTION only to the
existing canonical docs/BACKLOG.md checkpoint.

## Verified publication readback — ATL-004AJ

All conditional research gates passed on KIRAA for exact **clean**
commit b7092d39483490a2fc9f1233dad5bc80627b8952.
[Final main CI 44821380181](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/actions/runs/44821380181)
was 4/4 PASS on Ubuntu/Windows Python 3.10/3.12. The remote
annotated tag v0.5.0.dev1 **peels to that same commit**.
The local suite discovered 333 tests: 330 PASS and three existing
Windows symlink-privilege SKIPs. Installed wheel console/module smoke,
MIT-only source archive inventory, wheel rebuilt from source and
same-runner SOURCE_DATE_EPOCH wheel byte identity all PASS.

| GitHub artifact | Bytes | SHA-256 (actual uploaded/downloaded bytes) |
| --- | ---: | --- |
| kira_agent_trace_lab-0.5.0.dev1-py3-none-any.whl | 32116 | 9f1ce1a1ebdd036cc42572eb674d508d690fee2e638b79c702b9b784a8040ec3 |
| kira_agent_trace_lab-0.5.0.dev1.tar.gz | 49338 | 69d9a4dbee40c18b5fdfa7aede07cc19b01a1236a4ade2d77f1d8ea7c692d5f0 |
| SHA256SUMS.txt | 220 | 11e9364eb8bbd5ccc51915e22e494f3bf0bef2167f20923e970c363172c136e8 |

The three draft-release assets were **downloaded again from GitHub**
and compared byte-for-byte with KIRAA's verified tag-source assets.
SHA256SUMS.txt entries were rehashed against the downloaded wheel
and tarball before publication. GitHub then showed **draft=false,
prerelease=true** for
[the public dev1 research release](https://github.com/AkiyamaKira2003/kira-agent-trace-lab/releases/tag/v0.5.0.dev1).
The GitHub Latest-stable endpoint still returns **v0.4.0**;
the historical v0.5.0.dev0 prerelease and its assets were untouched.
SHA-256 demonstrates integrity of downloaded bytes, **not**
independent publisher identity.

**Decision: GO executed only for the dev1 research prerelease.**
Real-human grants, two authenticated independent reviewers,
representative attack/authorization labels, stable v0.5, PyPI and
qualified security integration into KiraShop remain **HOLD**.
