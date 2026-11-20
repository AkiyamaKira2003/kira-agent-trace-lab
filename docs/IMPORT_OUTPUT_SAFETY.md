# ATL-004R — Safe output contract for recorded trace importers

## Actual defect

Prior to ATL-004R, all three import subcommands (import-otlp,
import-swe and import-agentdojo) used a normal write operation that
silently replaced **any** pre-existing output file. This was
reproduced with a disposable, self-authored local file and did not
require a malicious trace. It could destroy unrelated work when
a wrong path was supplied, even though the recorded tool calls
themselves are never executed.

## Changed CLI contract

Each of the three trace importers now **creates output exclusively**
by default. If the named destination already exists, including a
symbolic link or a hard link, the command exits **2**, explains that
the output already exists, and preserves the existing file.

ATL-004S strengthens the first-write path: instead of creating the
final filename and writing directly into it, the importer first writes
and closes the entire JSON payload in a private same-directory
temporary file. Only after a successful write does it atomically
hard-link that complete file into a previously absent final output
name. Interrupted writes, failed hardlink creation, or a competing
creator cannot leave a partial final file. Temporary files are
cleaned up on those failures. The target filesystem must support
hardlinks in the selected output directory; otherwise creation
fails closed rather than falling back to unsafe partial writes.

To intentionally replace an existing regular output file, add
the optional **--overwrite** flag to the importer invocation.
This opt-in writes a private temporary file beside the destination
and atomically replaces the named output directory entry. It
rejects symbolic-link destinations. Replacing a hardlink alias does
not modify its original inode or any other hardlink destination.
Input source files and policy-suite files remain explicitly protected.

This is a deliberate compatibility adjustment: repeated commands
using the same --output path now require a fresh output filename
or **--overwrite**. The existing **evaluate** command's
output behavior is unchanged. The importer output still includes
argument values from recorded traces and should not be published
without privacy review. There is no runtime execution or replay.

This does not claim comprehensive protection from a hostile
concurrent filesystem actor changing directories between checks,
nor does it sanitize imported argument content.

## Reproduction and checks

From the project root:

    python -m unittest tests.test_import_output_safety -v
    python -m unittest discover -s tests -q
    python -m pip wheel --no-deps --wheel-dir artifacts/qa-import-safety .
    python -m scripts.verify_installed_wheel --wheel-dir artifacts/qa-import-safety

Tests cover all three formats: initial creation, repeated no-clobber
behavior, preservation of an unrelated existing file, explicit
replacement, hardlink isolation, input source protection and
symbolic-link refusal. The real symbolic-link integration test
skips when Windows runner policy denies symlink creation; a
mock-based test still covers the guard on every platform.
Three additional fault-injection tests cover interrupted temporary
writes, failed default hardlink publication and failed explicit
atomic replacement, asserting that only complete outputs are
visible and cleanup does not modify existing destination content.

The standard GitHub Actions matrix checks Python 3.10/3.12 on
Windows and Ubuntu. A passing synthetic fixture is a functional
regression test, **not** proof of independent human authorization
or agent-safety efficacy.
