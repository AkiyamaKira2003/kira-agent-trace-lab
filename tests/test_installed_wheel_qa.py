"""Security and correctness controls for installed-wheel reproducibility checks."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from agent_trace_lab.schema import SuiteError
from agent_trace_lab.engine import evaluate_suite
from agent_trace_lab.schema import load_suite
from scripts.verify_installed_wheel import (
    REQUIRED_WHEEL_MEMBERS, _execute, validate_evaluation, wheel_members,
    RELEASE_LINKS, installed_console_path, validate_console_equivalence,
    validate_release_metadata, source_project_version,
    validate_import_output_contract,
)

ROOT = Path(__file__).resolve().parents[1]
VERSION = source_project_version()
WHEEL_NAME = f"kira_agent_trace_lab-{VERSION}-py3-none-any.whl"
DIST_INFO_PREFIX = f"kira_agent_trace_lab-{VERSION}.dist-info/"


def make_wheel(directory: Path, *, members: list[str] | None = None) -> Path:
    path = directory / WHEEL_NAME
    with zipfile.ZipFile(path, "w") as archive:
        for name in members if members is not None else sorted(REQUIRED_WHEEL_MEMBERS):
            archive.writestr(name, "# harmless synthetic placeholder\n")
    return path


def make_release_metadata_wheel(
    directory: Path, *, changes: dict[str, bytes] | None = None,
    omissions: set[str] | None = None,
) -> Path:
    prefix = DIST_INFO_PREFIX
    header = (
        "Metadata-Version: 2.4\n"
        "Name: kira-agent-trace-lab\n"
        f"Version: {VERSION}\n"
        "License-Expression: MIT\n"
        "License-File: LICENSE\n"
        "Requires-Python: >=3.10\n"
    )
    for label, url in sorted(RELEASE_LINKS):
        header += f"Project-URL: {label}, {url}\n"
    payload = {
        prefix + "METADATA": header.encode("utf-8"),
        prefix + "WHEEL": b"Wheel-Version: 1.0\nTag: py3-none-any\n",
        prefix + "entry_points.txt": (
            b"[console_scripts]\nagent-trace-lab = agent_trace_lab.cli:main\n"
        ),
        prefix + "licenses/LICENSE": (
            b"MIT License\n\nPermission is hereby granted, free of charge"
        ),
    }
    payload.update(changes or {})
    path = directory / WHEEL_NAME
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in payload.items():
            if name not in (omissions or set()):
                archive.writestr(name, value)
    return path


class InstalledWheelQATests(unittest.TestCase):
    def test_installed_import_bytes_and_explicit_overwrite_contract(self):
        before = json.dumps({"cases": [{"id": "old", "trace": [{"tool": "read"}]}]}).encode()
        after = json.dumps({"cases": [{"id": "new", "trace": [{"tool": "read"}]}]}).encode()
        validate_import_output_contract(before, before, after, "old", "new")

    def test_installed_import_contract_rejects_unexpected_mutations(self):
        before = json.dumps({"cases": [{"id": "old", "trace": [{"tool": "read"}]}]}).encode()
        after = json.dumps({"cases": [{"id": "new", "trace": [{"tool": "read"}]}]}).encode()
        cases = (
            (before, b"overwritten without authorization", after),
            (before, before, before),
            (before, before, b"invalid json"),
            (before, before, b'{"cases": null}'),
            (before, before, json.dumps({"cases": [{"id": "new", "trace": []}]}).encode()),
            (before, before, json.dumps({"cases": [{"id": "wrong", "trace": [{"tool": "read"}]}]}).encode()),
        )
        for pre, blocked, forced in cases:
            with self.subTest(blocked=blocked, forced=forced), self.assertRaises(SuiteError):
                validate_import_output_contract(pre, blocked, forced, "old", "new")

    def test_expected_package_members_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = make_wheel(Path(directory))
            self.assertEqual(wheel_members(path), set(REQUIRED_WHEEL_MEMBERS))

    def test_script_and_local_sensitive_artifacts_not_packaged(self):
        for extra in ("scripts/verify_installed_wheel.py",
                      "docs/agentdojo_argument_shapes.json",
                      "artifacts/private.json", "examples/private.json", ".env"):
            with self.subTest(member=extra), tempfile.TemporaryDirectory() as directory:
                path = make_wheel(Path(directory), members=[*REQUIRED_WHEEL_MEMBERS, extra])
                if extra == ".env":
                    # .env is directly rejected as a forbidden suffix
                    pass
                with self.assertRaises(SuiteError):
                    wheel_members(path)

    def test_traversal_and_absolute_members_rejected(self):
        for extra in ("../private.txt", "/absolute/path"):
            with self.subTest(member=extra), tempfile.TemporaryDirectory() as directory:
                path = make_wheel(Path(directory), members=[*REQUIRED_WHEEL_MEMBERS, extra])
                with self.assertRaisesRegex(SuiteError, "unsafe"):
                    wheel_members(path)

    def test_windows_separator_rejected_if_exposed_by_zip_reader(self):
        # Windows ZipInfo normalizes real archive backslashes to '/'. Stub
        # namelist to exercise our explicit fallback defense nonetheless.
        with tempfile.TemporaryDirectory() as directory:
            path = make_wheel(Path(directory))
            with patch("scripts.verify_installed_wheel.zipfile.ZipFile") as reader:
                reader.return_value.__enter__.return_value.namelist.return_value = [
                    *REQUIRED_WHEEL_MEMBERS, "agent_trace_lab" + chr(92) + "secret.py",
                ]
                with self.assertRaisesRegex(SuiteError, "unsafe"):
                    wheel_members(path)

    def test_missing_required_cli_or_importer_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            members = sorted(REQUIRED_WHEEL_MEMBERS - {"agent_trace_lab/agentdojo.py"})
            path = make_wheel(Path(directory), members=members)
            with self.assertRaisesRegex(SuiteError, "missing"):
                wheel_members(path)

    def test_malformed_or_nonwheel_file_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / WHEEL_NAME
            bad.write_bytes(b"not a zip archive")
            with self.assertRaisesRegex(SuiteError, "valid wheel"):
                wheel_members(bad)
            bad.rename(Path(directory) / "something_else.zip")
            with self.assertRaisesRegex(SuiteError, "wheel path"):
                wheel_members(Path(directory) / "something_else.zip")

    def test_release_metadata_checks_real_distributable_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = make_release_metadata_wheel(Path(directory))
            self.assertEqual(validate_release_metadata(path), VERSION)
            self.assertEqual(source_project_version(), VERSION)

    def test_release_metadata_rejects_different_source_version(self):
        with tempfile.TemporaryDirectory() as directory:
            path = make_release_metadata_wheel(Path(directory))
            with patch("scripts.verify_installed_wheel.source_project_version",
                       return_value="0.5.0.dev999"):
                with self.assertRaisesRegex(SuiteError, "checked-out source"):
                    validate_release_metadata(path)

    def test_release_metadata_fails_closed_on_omitted_document(self):
        base = DIST_INFO_PREFIX
        for missing in ("METADATA", "WHEEL", "entry_points.txt", "licenses/LICENSE"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                path = make_release_metadata_wheel(
                    Path(directory), omissions={base + missing},
                )
                with self.assertRaises(SuiteError):
                    validate_release_metadata(path)

    def test_release_metadata_rejects_unverified_distribution_claims(self):
        base = DIST_INFO_PREFIX
        for name, fragment in (
            ("wrong_version", "Version: 0.4.0\n"),
            ("missing_repository_url", "Project-URL: Repository, "),
            ("unexpected_runtime_dependency", "Requires-Dist: external-pkg>=1\n"),
            ("changed_license", "License-Expression: Apache-2.0\n"),
        ):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                path = make_release_metadata_wheel(Path(directory))
                with zipfile.ZipFile(path) as archive:
                    metadata = archive.read(base + "METADATA").decode("utf-8")
                    data = {key: archive.read(key) for key in archive.namelist()}
                if name == "wrong_version":
                    metadata = metadata.replace(f"Version: {VERSION}\n", fragment)
                elif name == "missing_repository_url":
                    metadata = "\n".join(
                        line for line in metadata.split("\n")
                        if not line.startswith(fragment)
                    )
                elif name == "unexpected_runtime_dependency":
                    metadata += fragment
                else:
                    metadata = metadata.replace("License-Expression: MIT\n", fragment)
                data[base + "METADATA"] = metadata.encode("utf-8")
                with zipfile.ZipFile(path, "w") as archive:
                    for key, value in data.items():
                        archive.writestr(key, value)
                with self.assertRaisesRegex(SuiteError, "declarations"):
                    validate_release_metadata(path)

    def test_release_metadata_rejects_nonstandard_entrypoint_or_tags(self):
        base = DIST_INFO_PREFIX
        for member, value in (
            ("entry_points.txt", b"[console_scripts]\nother = something:else"),
            ("WHEEL", b"Wheel-Version: 1.0\nTag: cp312-win_amd64"),
            ("licenses/LICENSE", b"not an MIT license"),
        ):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as directory:
                path = make_release_metadata_wheel(
                    Path(directory), changes={base + member: value},
                )
                with self.assertRaisesRegex(SuiteError, "inconsistent"):
                    validate_release_metadata(path)

    def test_json_summary_require_exact_fixture_matches(self):
        validate_evaluation({"summary": {"total": 8, "matched": 8}}, 8)
        for bad in (
            None, {}, {"summary": None},
            {"summary": {"total": 8, "matched": 7}},
            {"summary": {"total": True, "matched": 8}},
            {"summary": {"total": 8, "matched": "8"}},
        ):
            with self.subTest(value=bad):
                with self.assertRaises(SuiteError):
                    validate_evaluation(bad, 8)

    def test_failed_cli_does_not_leak_subprocess_output(self):
        failing = subprocess.CompletedProcess(
            args=["python"], returncode=2, stdout="SECRET-SENTINEL",
            stderr="PRIVATE-RECIPIENT-ADDRESS",
        )
        with patch("scripts.verify_installed_wheel.subprocess.run", return_value=failing):
            with self.assertRaises(SuiteError) as error:
                _execute(["python"], Path("."), {})
        self.assertNotIn("SECRET-SENTINEL", str(error.exception))
        self.assertNotIn("PRIVATE-RECIPIENT-ADDRESS", str(error.exception))

    def test_console_launcher_is_found_under_pip_target_bin_on_both_platforms(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / "bin").mkdir()
            windows = site / "bin" / "agent-trace-lab.exe"
            unix = site / "bin" / "agent-trace-lab"
            windows.write_bytes(b"synthetic executable placeholder")
            unix.write_bytes(b"#!/usr/bin/env python\n")
            unix.chmod(0o755)
            self.assertEqual(installed_console_path(site, "nt"), windows)
            with patch("scripts.verify_installed_wheel.os.access", return_value=True):
                self.assertEqual(installed_console_path(site, "posix"), unix)

    def test_missing_or_unsupported_console_launcher_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            with self.assertRaisesRegex(SuiteError, "absent or unsafe"):
                installed_console_path(site, "nt")
            with self.assertRaisesRegex(SuiteError, "unsupported"):
                installed_console_path(site, "unexpected_platform")
            (site / "bin").mkdir()
            unix = site / "bin" / "agent-trace-lab"
            unix.write_bytes(b"not executable")
            with patch("scripts.verify_installed_wheel.os.access", return_value=False):
                with self.assertRaisesRegex(SuiteError, "absent or unsafe"):
                    installed_console_path(site, "posix")

    def test_console_vs_module_verdict_comparison_rejects_false_equivalence(self):
        permissive = evaluate_suite(load_suite(ROOT / "examples" / "demo_permissive.json"))
        scoped = evaluate_suite(load_suite(ROOT / "examples" / "demo_task_scoped.json"))
        validate_console_equivalence(permissive, scoped,
                                     copy.deepcopy(permissive), copy.deepcopy(scoped))
        for section, change in (
            ("permissive", "schema_version"),
            ("permissive", "summary"),
            ("scoped", "schema_version"),
            ("scoped", "summary"),
        ):
            with self.subTest(section=section, field=change):
                observed_broad = copy.deepcopy(permissive)
                observed_scoped = copy.deepcopy(scoped)
                altered = observed_broad if section == "permissive" else observed_scoped
                if change == "schema_version":
                    altered[change] = "other"
                else:
                    altered["summary"]["accuracy"] = -1
                with self.assertRaises(SuiteError):
                    validate_console_equivalence(permissive, scoped,
                                                 observed_broad, observed_scoped)


if __name__ == "__main__":
    unittest.main()
