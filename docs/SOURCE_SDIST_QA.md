# ATL-004U — Source distribution integrity and privacy boundary

This is a **development release-preflight control** for version
0.5.0.dev0, not evidence of agent-security effectiveness or
permission ground truth.

## Reproduced packaging gap

The default setuptools sdist contained **44 entries**, including
22 Python test files. It did **not** contain the examples, research
scripts or documents those tests reference. The source tarball was
therefore not self-contained for test reproduction, despite being
usable to install the library.

The Git repository remains the canonical place to run the tests
and external/provenance research. The sdist is now deliberately a
**minimal MIT-licensed installation source archive**:

- Package Python code, README, pyproject, MANIFEST and MIT LICENSE
  remain; generated package metadata is included.
- Tests, docs, scripts, examples, artifacts and private env files do
  not ship. In particular, the CC BY 4.0 adapted AgentDrift fixture
  is not redistributed in the MIT-only sdist.
- README points source-archive users back to the original repository
  to obtain the examples, test fixtures, evidence and their separate
  rights/attribution notices.

## Fail-closed verifier

The standard-library scripts/verify_source_sdist.py requires one
archive with source-matching version and enforces limited compressed
and unpacked sizes, member count, unique safe paths, no symlink or
special-device entries, no source-only/private paths, a complete
MIT license, source content equality for package files (normalizing
only Windows CRLF versus LF checkout line endings) and
correct source metadata (name, version, Python range, links, zero
runtime dependencies).

ATL-004V confirmed that a previously verified archive could fail
the original byte comparison after changing Git branches on KIRAA
with core.autocrlf=true. The code and archive were unchanged, but
README and MANIFEST.in worktree line endings differed. The auditor
now considers only LF and CRLF equivalent; arbitrary carriage returns,
content edits, removed fields and injected data still fail. This
prevents incorrect failure claims when verifying an artifact across
platforms or checkouts without weakening content-level validation.

The audited KIRAA archive after the manifest fix contained **22
entries** with zero forbidden research/private paths. The built
tarball was passed through pip wheel, and the resulting wheel passed
the separate outside-source isolated installation/CLI smoke check.
These are **local functional packaging proofs**, not independent
human review or production security claims.

CI uses the pinned development-only build==1.2.2.post1 frontend to
create an isolated sdist on Windows and Ubuntu, Python 3.10 and 3.12.
It validates the source archive, rebuilds a wheel from the archive
and runs the installed-wheel smoke. Build tools may fetch their
declared build dependencies; runtime remains dependency free and
installed wheel smoke uses no network.

These checks cannot guarantee arbitrary future additions are
correctly licensed, and they do not constitute a content-level privacy
review of real third-party traces. **No v0.5 stable release or
KiraShop showcase is implied.** ATL-004/006 independent grant
and evaluation gates remain unmet.
