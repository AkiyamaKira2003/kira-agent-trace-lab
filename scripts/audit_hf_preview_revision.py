"""Recheck a cached SWE preview row without publishing or executing its contents.

The Dataset Viewer X-Revision header is *server-reported* provenance, not
cryptographic proof that the row was independently decoded from Hub Parquet.
This script deliberately does not download shards or print raw messages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib import request


DATASET = "nvidia/Open-SWE-Traces"
PREVIEW_URL = (
    "https://datasets-server.huggingface.co/first-rows?"
    "dataset=nvidia/Open-SWE-Traces&config=v1.0&split=sweagent"
)
MAX_JSON_BYTES = 2 * 1024 * 1024


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_source_metadata(metadata: Any, revision: str) -> None:
    if not isinstance(metadata, dict) or metadata.get("sha") != revision:
        raise ValueError("Hub revision metadata does not match the requested commit")
    card = metadata.get("cardData")
    if not isinstance(card, dict) or card.get("license") != "cc-by-4.0":
        raise ValueError("dataset license is missing or differs from the audited CC BY 4.0")


def validate_preview(
    preview: Any, header_revision: str | None, revision: str, local_row: Any
) -> dict[str, str]:
    if header_revision != revision:
        raise ValueError("Dataset Viewer X-Revision does not match the pinned commit")
    if not isinstance(preview, dict):
        raise ValueError("preview response must be an object")
    rows = preview.get("rows")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise ValueError("preview has no first row")
    first = rows[0]
    if first.get("row_idx") != 0 or first.get("truncated_cells") != []:
        raise ValueError("first preview row is missing, reordered or truncated")
    row = first.get("row")
    if not isinstance(row, dict) or not isinstance(local_row, dict):
        raise ValueError("preview/local row must be JSON objects")
    preview_bytes = canonical_bytes(row)
    if preview_bytes != canonical_bytes(local_row):
        raise ValueError("preview row differs from locally cached evidence")
    return {
        "sha256": hashlib.sha256(preview_bytes).hexdigest(),
        "bytes": str(len(preview_bytes)),
        "source_repo_license": str(row.get("license", "unverified")),
    }


def fetch_json(url: str) -> tuple[Any, str | None]:
    req = request.Request(url, headers={"Accept": "application/json", "User-Agent": "KiraAgentTraceLab-ProvenanceAudit/1.0"})
    with request.urlopen(req, timeout=15) as response:
        revision = response.headers.get("X-Revision")
        raw = response.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("remote JSON exceeds the 2 MiB safety limit")
    return json.loads(raw), revision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-row", type=Path, required=True, help="Private ignored row JSON on this machine")
    parser.add_argument("--revision", required=True, help="Exact 40-hex-character Hub commit")
    parser.add_argument("--expected-sha256", required=True, help="Previously recorded canonical row SHA-256")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision) or not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha256):
        parser.error("revision must be 40 lowercase hex digits; SHA-256 must be 64 lowercase hex digits")
    try:
        if args.local_row.stat().st_size > MAX_JSON_BYTES:
            raise ValueError("local row exceeds the 2 MiB safety limit")
        local_row = json.loads(args.local_row.read_text(encoding="utf-8"))
        metadata_url = f"https://huggingface.co/api/datasets/{DATASET}/revision/{args.revision}"
        metadata, _ = fetch_json(metadata_url)
        validate_source_metadata(metadata, args.revision)
        preview, header_revision = fetch_json(PREVIEW_URL)
        evidence = validate_preview(preview, header_revision, args.revision, local_row)
        if evidence["sha256"] != args.expected_sha256:
            raise ValueError("row digest differs from the previously recorded hash")
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "NOT_VERIFIED", "error": str(exc)}))
        return 1
    print(json.dumps({
        "status": "SERVER_ATTESTED_PREVIEW_MATCH",
        "dataset": DATASET,
        "pinned_commit": args.revision,
        "preview_x_revision": header_revision,
        "row_sha256": evidence["sha256"],
        "row_canonical_bytes": int(evidence["bytes"]),
        "dataset_license": "CC BY 4.0",
        "source_repo_license": evidence["source_repo_license"],
        "source_parquet_row_independently_verified": False,
        "trace_executed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
