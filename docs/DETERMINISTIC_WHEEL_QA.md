# ATL-004M — Two-build deterministic wheel experiment

The installed-wheel smoke gate verifies actual installation and CLI execution.
It does not alone guarantee that repeated packaging yields identical bytes.

Reproduce from the source checkout with Python 3.10+:

    python -m scripts.verify_reproducible_wheel
    python -m unittest discover -s tests -q

This source-only checker reads the current Git commit timestamp and sets
SOURCE_DATE_EPOCH for two separate PEP 517 wheel-build commands. Each writes
to a different temporary directory under ignored artifacts/. The isolated
build backend may download the declared setuptools build dependency, while
application runtime dependencies are excluded. No recorded agent tools execute.

The checker requires the expected versioned wheel filename, complete package
member sets, byte length and identical SHA-256 hashes. Failures do not print
raw build subprocess outputs that might contain user data.

On KIRAA with local Python 3.12, using Git epoch 1795201363, two builds
of the same revision yielded SHA-256:

    f0216b0406004a3f05c6ffe507cf5e79639066e133557c14219b5719632c77b9

This proves within-environment repetition for that revision, not
cross-machine or cross-platform byte-for-byte equality. CI repeats the
check on Ubuntu/Windows and Python 3.10/3.12. Each job compares its two
local builds; hashes are not required to match between different jobs.
Build dependency versions, Python versions or Git revisions can change
the resulting hash. No real-agent authorization or safety performance
is inferred from this packaging result.
