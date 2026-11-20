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
