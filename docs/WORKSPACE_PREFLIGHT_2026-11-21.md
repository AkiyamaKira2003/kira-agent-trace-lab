# ATL-004BT: Windows workspace preflight and flagship candidate gate

Date: 2026-11-21. Machine: KIRAA, KPC Core. Scope: source-only operational
utility in the existing Agent Trace Lab campaign. No new public project.

## Demand and existing alternatives

- [Claude Code #88862](https://github.com/anthropics/claude-code/issues/88862)
  reports parallel agent sessions sharing a Windows checkout and colliding.
- [Hermes Agent #46303](https://github.com/NousResearch/hermes-agent/issues/46303)
  reports concurrent-session state and worktree cross-contamination.
- [Go MCP SDK #1188](https://github.com/modelcontextprotocol/go-sdk/issues/1188)
  records dual-protocol tool-schema incompatibility. It has multiple
  interested contributors and remains a distinct SDK ownership problem.
- [beyond10x/worktree](https://github.com/beyond10x/worktree) already
  provides durable worktree leases and recovery-aware cleanup. Its
  documentation describes live process observation on Linux through
  /proc, but not equivalent Windows process coverage.
- [Cisco MCP contract CLI](https://github.com/cisco-open/mcptoolkit-contract)
  and [mcp-diff](https://github.com/paulochastinet/mcp-diff) already
  validate/diff MCP contracts. [Proofboard](https://proofboard.io/) and
  [CodeRepute](https://coderepute.dev/) cover portfolio evidence.

Prospective **subjective, not measured** scores for a new public project.
Rubric weights: demand 20, originality 20, depth 20, verifiability 15,
rights/privacy 10, feasibility 10, portfolio signal 5 (total 100).

| Candidate | Demand | Original | Depth | Verify | Rights | Feasible | Signal | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Windows-aware multi-agent worktree guardian | 18 | 11 | 17 | 12 | 10 | 7 | 4 | **79** |
| MCP schema compatibility diff | 17 | 5 | 14 | 12 | 9 | 8 | 3 | **68** |
| Verified developer contribution profile | 16 | 5 | 14 | 11 | 9 | 8 | 3 | **66** |

NONE clears the >=85/100 admission gate for a NEW public repository.
Source evidence demonstrates a problem, not distinctive product adoption.

## KIRAA read-only experiment and vertical slice

The original direct PowerShell Get-CimInstance Win32_Process observation,
combined with Git status, found:

| Existing checkout | Git dirty | Attached Git worktrees | Executable processes located within checkout |
|---|---:|---:|---:|
| PiPClickThrough | 0 | 1 | **1 (PID 34140)** |
| FarmTimerOverlay | 0 | 1 | 0 observed |
| kira-agent-trace-lab before source editing | 0 | 1 | 0 observed |

This is an **observed live executable in an otherwise clean checkout**,
not an observed data-loss incident or proof of a concurrent agent session.
The PiP process, portable EXE and user settings were never touched.

The existing-campaign scripts/workspace_preflight.py implements a bounded
read-only check of one exact Git root/HEAD/branch, modified or untracked
file count and worktree count. It invokes Git with --no-optional-locks
to avoid optional index-refresh writes (see official
[Git status](https://git-scm.com/docs/git-status) documentation).
On Windows it invokes the local CIM provider and returns **only process IDs**
with executable paths in the checkout. Path containment is lexical,
case-insensitive and directory-boundary-aware, not a naive prefix check.
No process arguments, executable paths, filenames or file contents appear
in the JSON report.

Verdicts: HOLD for dirty working tree or observed resident executable;
REVIEW for unavailable/unsupported process visibility or multiple linked
worktrees; NO_OBSERVED_BLOCKER only when this particular probe saw none.
The CLI uses exit codes 3/2/0 for review-or-hold/error/no-observed-blocker.
These codes are operational hints, not permission to rebuild, deploy,
delete or reset user files.

**Limits:** CIM may omit protected executables, and executable-path matching
does not detect interpreted scripts, GUI browsers, IDE sessions, process
working directories, DLL locks or Git ownership. The snapshot has a
time-of-check/time-of-use race and is not a lease or concurrency lock.
On non-Windows hosts process visibility is unsupported and the tool
requests manual review. Never present exit 0 as a universal guarantee.

## Acceptance and successor engineering gate

Pure tests cover path boundaries, PID filtering, dirty/live precedence,
unknown process visibility, CLI privacy, errors and subdirectory rejection.
Temporary Git repository integration verifies that inspection preserves
commit HEAD and dirty contents. KIRAA live smoke checks must show PiP HOLD
and a clean idle checkout with no observed executable; the full Windows/
Ubuntu Python 3.10/3.12 CI matrix still gates the PR/merge.

Next flagship research should seek consented test scenarios demonstrating
**actual** multiple-session collisions on Windows and a distinct prevention/
recovery mechanism superior to incumbents. Without such evidence, keep new
public repository creation on HOLD; do not simply enlarge this heuristic.
