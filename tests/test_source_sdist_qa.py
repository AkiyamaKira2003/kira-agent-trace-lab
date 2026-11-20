"""ATL-004U: source releases must not package private data or omit source rights."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tarfile
import tempfile
import unittest

from agent_trace_lab.schema import SuiteError
from scripts.verify_installed_wheel import RELEASE_LINKS, ROOT, source_project_version
from scripts.verify_source_sdist import REQUIRED_FILES, verify_sdist

VERSION = source_project_version()
PREFIX = f"kira_agent_trace_lab-{VERSION}"


def make_source_archive(
    folder: Path,
    *, extra: dict[str, bytes] | None = None,
    missing: set[str] | None = None,
    changed: dict[str, bytes] | None = None,
    symlink: bool = False,
) -> Path:
    metadata = (
        "Metadata-Version: 2.4\nName: kira-agent-trace-lab\n"
        f"Version: {VERSION}\nLicense-Expression: MIT\n"
        "License-File: LICENSE\nRequires-Python: >=3.10\n"
    )
    for label, link in sorted(RELEASE_LINKS):
        metadata += f"Project-URL: {label}, {link}\n"
    data = {
        name: (metadata.encode("utf-8") if name == "PKG-INFO"
               else (ROOT / name).read_bytes())
        for name in REQUIRED_FILES
    }
    data.update(changed or {})
    data.update(extra or {})
    output = folder / (PREFIX + ".tar.gz")
    with tarfile.open(output, "w:gz") as archive:
        for name, body in sorted(data.items()):
            if name in (missing or set()):
                continue
            info = tarfile.TarInfo(PREFIX + "/" + name)
            info.size = len(body)
            archive.addfile(info, BytesIO(body))
        if symlink:
            info = tarfile.TarInfo(PREFIX + "/agent_trace_lab/external_link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/private"
            archive.addfile(info)
    return output


class SourceSdistQATests(unittest.TestCase):
    def test_minimal_mit_only_source_archive_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            details = verify_sdist(make_source_archive(Path(tmp)))
            self.assertEqual(details["status"], "SOURCE_SDIST_INVENTORY_PASS")
            self.assertFalse(details["private_or_third_party_records_bundled"])

    def test_rejects_missing_required_code_and_license(self):
        for missing in ("LICENSE", "MANIFEST.in", "pyproject.toml",
                        "agent_trace_lab/cli.py", "PKG-INFO"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                archive = make_source_archive(Path(tmp), missing={missing})
                with self.assertRaisesRegex(SuiteError, "missing"):
                    verify_sdist(archive)

    def test_rejects_sensitive_and_research_only_paths(self):
        for name in ("artifacts/private_trace.json", "examples/agentdrift_counterexamples.json",
                     "tests/test_engine.py", "docs/agentdojo_review_packet.json",
                     "scripts/audit_agentdojo_strata.py", "agent_trace_lab/.env",
                     "../external.json", ".git/config", "agent_trace_lab/__pycache__/x.pyc"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                archive = make_source_archive(
                    Path(tmp), extra={name: b"self-authored fake sensitive data"}
                )
                with self.assertRaisesRegex(SuiteError, "private|unsafe"):
                    verify_sdist(archive)

    def test_rejects_tar_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SuiteError, "unsafe"):
                verify_sdist(make_source_archive(Path(tmp), symlink=True))

    def test_rejects_source_drift_even_when_package_metadata_looks_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = make_source_archive(
                Path(tmp), changed={"agent_trace_lab/cli.py": b"changed code"}
            )
            with self.assertRaisesRegex(SuiteError, "differ"):
                verify_sdist(archive)

    def test_rejects_incorrect_license_and_version_declarations(self):
        for mutation in ("Version: 0.4.0", "License-Expression: Apache-2.0",
                         "Requires-Dist: unexpectedly-required-package"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                original = (
                    "Metadata-Version: 2.4\nName: kira-agent-trace-lab\n"
                    f"Version: {VERSION}\nLicense-Expression: MIT\n"
                    "License-File: LICENSE\nRequires-Python: >=3.10\n"
                )
                for label, url in sorted(RELEASE_LINKS):
                    original += f"Project-URL: {label}, {url}\n"
                if mutation.startswith("Requires-Dist"):
                    original += mutation + "\n"
                elif mutation.startswith("Version"):
                    original = original.replace(f"Version: {VERSION}", mutation)
                else:
                    original = original.replace("License-Expression: MIT", mutation)
                archive = make_source_archive(
                    Path(tmp), changed={"PKG-INFO": original.encode("utf-8")}
                )
                with self.assertRaisesRegex(SuiteError, "metadata"):
                    verify_sdist(archive)


if __name__ == "__main__":
    unittest.main()
