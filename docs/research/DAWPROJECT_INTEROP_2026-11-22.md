# DAWproject cross-DAW portability: evidence-gated creator research

Date: 2026-11-22. Campaign: ATL-004DF.
Status: RESEARCH_ONLY / NO_GO_NEW_REPO / OWNER_SELECTION_REQUIRED.

## User job and scope

Music producers transferring sessions between Bitwig, Studio One, Cubase and/or REAPER need to know whether audio, plug-in state, parameter automation, note placement and Clip Launcher data will survive. A file that opens but silently loses edits is not a successful handoff.

Research used only public official documentation, upstream source metadata and GitHub issue reports. It did NOT use a producer's sessions, run a DAW, benchmark a converter, export/import copyright audio, or prove a new tool works. DAWproject is an open MIT-licensed interchange specification: https://github.com/bitwig/dawproject.

## Verified public evidence

| Risk | Evidence | What it establishes, and limits |
| --- | --- | --- |
| Plug-in parameter automation disappears after source plug-in is uninstalled | https://github.com/bitwig/dawproject/issues/82 (OPEN, 2024-08-09) | Reporter provides VST3 steps for Bitwig export/reimport. It does not prove every DAW fails, nor that post-export recovery is possible. |
| External audio references have no content hash | https://github.com/bitwig/dawproject/issues/106 (OPEN, proposed 2026-11-18) | Optional SHA-256 reference hashes were already proposed upstream. This is not an unclaimed novel discovery, nor an already deployed standard extension. |
| ZIP layout can cause Cubase import trouble | https://github.com/bitwig/dawproject/issues/101 (OPEN, updated 2026-11-12) | Reporter describes Cubase 14+ incompatibility with data-descriptor ZIP archives. This is a vendor behavior claim, not proof such archives violate ZIP. |
| Studio One project MIDI items appear empty after REAPER conversion | https://github.com/git-moss/ProjectConverter/issues/26 (OPEN, 2026-10-12) | Source-relative MIDI note time and playStart offsets are implicated. Not locally reproduced. |
| Audio clips shift with seconds-vs-beats timebase | https://github.com/git-moss/ProjectConverter/issues/27 (OPEN, 2026-10-13) | Real user report includes timeUnit=seconds lanes. ProjectConverter changelog already mentions related fixes; current exact-version reproduction remains necessary. |
| Clip Launcher, DAW plug-in state and external media have version-specific limitations | https://www.bitwig.com/support/technical_support/dawproject-file-format-faqs-62/ and https://helpcenter.steinberg.de/hc/en-us/articles/25142209226642-DAWproject-Exchange-Cubasis-projects-with-Cubase-and-other-DAWs | Bitwig explicitly describes missing Studio One Clip Launcher read support for the versions in its FAQ. Steinberg warns that in Studio One 7.1.1 users must copy external files before packaging audio; Cubasis has limitations with scenes and automation. Avoid extending these statements to untested newer versions. |

## Existing implementations and licenses

- **DAWproject** (MIT): project interchange format and public schema; vendors interpret which data they can import.
- **DawVert** (GPL-3.0): multi-format DAW/project converter including DAWproject, REAPER, FL Studio and LMMS. https://github.com/DawVert/DawVert. Existing Cubase-format import issue: https://github.com/DawVert/DawVert/issues/32.
- **ProjectConverter** (LGPL-3.0): REAPER to/from DAWproject, including Clip Launcher scene-to-arrangement flattening. Its manual describes missing plug-in parameter envelopes, complex routing and other limitations. https://github.com/git-moss/ProjectConverter.
- **session-state-analyzer** (MIT): provenance-first session state inspection; read-only source/metadata scope, not runtime tested here. https://github.com/ColonelKernel/session-state-analyzer.
- **QylosLab** and **DAW Converter** advertise audio/media and plugin inventories, missing paths, project scans or repair. These claims are NOT verified through local tests, and their commercial licensing/pricing was not independently confirmed. https://qyloslab.com/download/ and https://www.dawconverter.com/.
- Libraries such as https://github.com/roex-audio/dawproject-py (MIT) and https://github.com/bkbkb-net/dawproject support reuse rather than authoring a new ZIP/XML format parser.

## Gate scores (subjective, not measured market data)

Weights in order: real usefulness 25 / technical depth 25 / differentiation 15 / portfolio breadth 15 / zero mandatory prototype cost 10 / demonstrability 10.

| Idea | Score | Admission decision |
| --- | --- | --- |
| Read-only preflight for media references, file identities and DAW compatibility | 83 = 24+21+7+14+9+8 | HOLD: plausible demand, but upstream hash proposal and existing tools overlap; no paired-session test. |
| Detect lost automation/MIDI semantics by comparing source and target states | 78 = 24+22+5+13+7+7 | HOLD: needs authorized source DAWs and authentic test sessions; post-export information may already be lost. |
| Generic Clip Launcher-to-arrangement or timebase converter | 73 = 22+19+4+12+8+8 | NO GO: ProjectConverter already implements scene flattening; isolated bugs do not justify another clone. |

None reaches the minimum new-project gate of 85/100. More importantly, the current owner directive requires individually choosing an idea in Kira-Creator-Project-Atlas before starting any creator product. No new creator repository, source, product fixture, website, KPCenter registration, release, issue or PR was created by this research.

## Only-after-approval falsifiable acceptance sketch

Compare two specifically authorized self-authored DAW sessions in the exact versions being targeted. Record a source/target manifest of audio content hashes, plug-in identifiers and settings, automation curves, note offsets, tempo maps and scenes; perform real exports/imports; identify exact losses and explicitly mark UNKNOWN where the source application does not expose information. Test negative controls with one missing sample and an unavailable plug-in. A new project must outperform existing migration tools on that benchmark and have license-compatible scope. The present task has NOT performed that experiment.

**Decision:** research complete; do not begin creator-product coding. Continue independently authorized Agent Trace Lab source reliability/testing instead, within its normal review and release gates.
