"""Check an installable MIT-only source archive without extracting it."""

from __future__ import annotations

import argparse
from email.parser import BytesParser
from email.policy import default as email_policy
import hashlib
import json
from pathlib import Path
import tarfile

from agent_trace_lab.schema import SuiteError
from scripts.verify_installed_wheel import (
    RELEASE_LINKS, ROOT, source_project_version,
)

MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_UNPACKED_BYTES = 8 * 1024 * 1024
MAX_MEMBERS = 200
FORBIDDEN_PARTS = frozenset({
    "artifacts", "docs", "examples", "scripts", "tests",
    "__pycache__", ".git", ".venv",
})
SOURCE_MODULES = (
    "__init__.py", "__main__.py", "agentdojo.py", "cli.py",
    "engine.py", "otlp.py", "schema.py", "swe.py",
)
REQUIRED_FILES = frozenset({
    "LICENSE", "MANIFEST.in", "README.md", "pyproject.toml",
    "PKG-INFO", *(f"agent_trace_lab/{name}" for name in SOURCE_MODULES),
})


def verify_sdist(path: Path) -> dict[str, object]:
    version = source_project_version()
    root = f"kira_agent_trace_lab-{version}"
    if (not path.is_file()
            or path.name != root + ".tar.gz"
            or not 0 < path.stat().st_size <= MAX_ARCHIVE_BYTES):
        raise SuiteError("source archive version/path/size not accepted")

    try:
        with tarfile.open(path, mode="r:gz") as archive:
            entries = archive.getmembers()
            if not 0 < len(entries) <= MAX_MEMBERS:
                raise SuiteError("source archive member count outside limit")
            seen: set[str] = set()
            sources: dict[str, bytes] = {}
            total = 0
            for item in entries:
                name = item.name.rstrip("/")
                parts = name.split("/")
                if (name in seen or parts[0] != root
                        or "\\" in name or name.startswith("/")
                        or any(part in ("", ".", "..") for part in parts)
                        or any(part.lower() in FORBIDDEN_PARTS for part in parts[1:])
                        or any(part.lower().startswith(".env") for part in parts[1:])
                        or not (item.isfile() or item.isdir())):
                    raise SuiteError("unsafe, duplicate or private source archive entry")
                seen.add(name)
                if not item.isfile():
                    continue
                total += item.size
                if item.size < 0 or total > MAX_UNPACKED_BYTES:
                    raise SuiteError("unpacked source archive exceeds size ceiling")
                relative = "/".join(parts[1:])
                if relative in REQUIRED_FILES:
                    handle = archive.extractfile(item)
                    if handle is None:
                        raise SuiteError("required source archive file unreadable")
                    sources[relative] = handle.read()
            if not REQUIRED_FILES <= sources.keys():
                raise SuiteError("source archive missing required code/legal files")
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise SuiteError("source archive is unreadable or malformed") from exc

    for relative in ("LICENSE", "README.md", "pyproject.toml", "MANIFEST.in",
                     *(f"agent_trace_lab/{name}" for name in SOURCE_MODULES)):
        if sources[relative] != (ROOT / relative).read_bytes():
            raise SuiteError("source archive bytes differ from local source")
    if (b"MIT License" not in sources["LICENSE"]
            or b"Permission is hereby granted" not in sources["LICENSE"]):
        raise SuiteError("source license notice missing")

    metadata = BytesParser(policy=email_policy).parsebytes(sources["PKG-INFO"])
    urls = set()
    for value in metadata.get_all("Project-URL", []):
        if ", " not in value:
            raise SuiteError("source package has malformed project URL")
        urls.add(tuple(value.split(", ", 1)))
    if (metadata.get("Name") != "kira-agent-trace-lab"
            or metadata.get("Version") != version
            or metadata.get("License-Expression") != "MIT"
            or "LICENSE" not in metadata.get_all("License-File", [])
            or metadata.get("Requires-Python") != ">=3.10"
            or metadata.get_all("Requires-Dist")
            or not RELEASE_LINKS <= urls):
        raise SuiteError("source package metadata does not match release contract")
    return {
        "status": "SOURCE_SDIST_INVENTORY_PASS",
        "version": version,
        "members_checked": len(entries),
        "compressed_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "private_or_third_party_records_bundled": False,
        "runtime_security_effectiveness_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdist-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        paths = list(args.sdist_dir.glob("kira_agent_trace_lab-*.tar.gz"))
        if len(paths) != 1:
            raise SuiteError("expected exactly one local source archive")
        print(json.dumps(verify_sdist(paths[0]), sort_keys=True))
    except (SuiteError, OSError, ValueError, EOFError) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
