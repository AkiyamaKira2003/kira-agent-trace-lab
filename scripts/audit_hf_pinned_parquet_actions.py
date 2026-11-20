"""Verify the FIRST recorded SWE row's actions against immutable Hub Parquet.

Optional research tool (requires PyArrow), not part of the offline evaluator.
Only selected Parquet columns are fetched through checked HTTP byte ranges.
System prompts, natural-language messages and code patches are NOT fetched.
The result proves action-record equivalence, NOT authorization or full-row bytes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
from urllib import request

from agent_trace_lab.swe import import_swe_row
from scripts.audit_hf_preview_revision import canonical_bytes, fetch_json, validate_source_metadata


REVISION = "4fa4c2ae9afc6b397bc50391d43450c79993c138"
DATASET = "nvidia/Open-SWE-Traces"
SHARD_PATH = "data/sweagent/minimax_m25/swe-rebench-v2/train-00000-of-00019.parquet"
SHARD_BYTES = 208152116
ROW_DIGEST = "5dd6520877d2b0b95e6e3bfa39f868d36a3429c821f7d768b200a6ca8edebb40"
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
URL = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{SHARD_PATH}"
IDENTITY_FIELDS = ("instance_id", "repo", "license", "trajectory_id", "hf_dataset_name")
ACTION_LEAVES = (
    "messages.list.element.role",
    "messages.list.element.tool_calls.list.element.function.name",
    "messages.list.element.tool_calls.list.element.function.arguments",
    "messages.list.element.tool_calls.list.element.type",
)


class BoundedRangeFile(io.RawIOBase):
    """Seekable read-only remote Parquet file with an absolute transfer budget."""

    def __init__(self, url: str, size: int, budget: int = MAX_DOWNLOAD_BYTES):
        super().__init__()
        self.url, self.size, self.budget = url, size, budget
        self.offset = 0
        self.transferred = 0
        self.requests = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.offset

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence not in (0, 1, 2):
            raise ValueError("invalid seek mode")
        pos = (0 if whence == 0 else self.offset if whence == 1 else self.size) + offset
        if not 0 <= pos <= self.size:
            raise OSError("out-of-bounds Parquet seek")
        self.offset = pos
        return pos

    def read(self, n: int = -1) -> bytes:
        if n == -1:
            n = self.size - self.offset
        if n < 0:
            raise ValueError("invalid read length")
        n = min(n, self.size - self.offset)
        if n == 0:
            return b""
        if self.transferred + n > self.budget:
            raise OSError("remote transfer would exceed configured byte budget")
        start, end = self.offset, self.offset + n - 1
        req = request.Request(self.url, headers={
            "Range": f"bytes={start}-{end}",
            "User-Agent": "KiraAgentTraceLab-PinnedParquetAudit/1.0",
        })
        with request.urlopen(req, timeout=20) as response:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{self.size}":
                raise OSError("server refused exact pinned-file byte range")
            data = response.read(n + 1)
        if len(data) != n:
            raise OSError("Parquet range response length mismatch")
        self.offset += n
        self.transferred += n
        self.requests += 1
        return data

    def readinto(self, buffer: bytearray | memoryview) -> int:
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def compare_actions(source: dict, saved: dict, identities: dict) -> dict:
    """Compare the precise fields consumed by the offline SWE importer."""
    if any(identities.get(key) != saved.get(key) for key in IDENTITY_FIELDS):
        raise ValueError("first pinned Parquet row identity differs from cached row")
    source_messages, cached_messages = source.get("messages"), saved.get("messages")
    if not isinstance(source_messages, list) or not isinstance(cached_messages, list):
        raise ValueError("source and cache must contain messages")
    if [m.get("role") for m in source_messages] != [m.get("role") for m in cached_messages]:
        raise ValueError("recorded message roles differ")
    policy = {"max_actions": 100, "tools": {"bash": {}, "str_replace_editor": {}, "submit": {}}}
    first = import_swe_row(source, policy=policy, case_id="pinned", expected="allow")["cases"][0]["trace"]
    second = import_swe_row(saved, policy=policy, case_id="pinned", expected="allow")["cases"][0]["trace"]
    if first != second:
        raise ValueError("pinned source actions do not match cached action sequence")
    return {
        "message_count": len(source_messages),
        "action_count": len(first),
        "action_names": dict(sorted(Counter(event["tool"] for event in first).items())),
        "canonical_action_sha256": hashlib.sha256(canonical_bytes(first)).hexdigest(),
    }


def run_audit(local_row: Path, *, pq: object) -> dict:
    if local_row.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("cached row exceeds 2 MiB")
    saved = json.loads(local_row.read_text(encoding="utf-8"))
    if hashlib.sha256(canonical_bytes(saved)).hexdigest() != ROW_DIGEST:
        raise ValueError("cached row does not match audited row SHA-256")
    meta_url = f"https://huggingface.co/api/datasets/{DATASET}/revision/{REVISION}"
    hub_metadata, _ = fetch_json(meta_url)
    validate_source_metadata(hub_metadata, REVISION)

    remote = BoundedRangeFile(URL, SHARD_BYTES)
    parquet = pq.ParquetFile(remote)
    if parquet.metadata.num_row_groups != 1 or parquet.metadata.row_group(0).num_rows != 2500:
        raise ValueError("pinned source shard row-group layout changed unexpectedly")
    first_group = parquet.metadata.row_group(0)
    allowed = set(IDENTITY_FIELDS) | set(ACTION_LEAVES)
    compressed = sum(first_group.column(i).total_compressed_size for i in range(first_group.num_columns)
                     if first_group.column(i).path_in_schema in allowed)
    if compressed + remote.transferred + 256 * 1024 > remote.budget:
        raise ValueError("selected column chunks exceed transfer budget")
    identities = parquet.read_row_group(0, columns=list(IDENTITY_FIELDS), use_threads=False).slice(0, 1).to_pylist()[0]
    actions = parquet.read_row_group(0, columns=list(ACTION_LEAVES), use_threads=False).slice(0, 1).to_pylist()[0]
    result = compare_actions(actions, saved, identities)
    if result["action_count"] != 48 or result["message_count"] != 97:
        raise ValueError("pinned sample shape changed")
    return {
        "status": "PINNED_PARQUET_ACTION_EQUIVALENCE_VERIFIED",
        "pinned_commit": REVISION,
        "source_parquet_path": SHARD_PATH,
        "source_license": identities["license"],
        "dataset_license": "CC BY 4.0",
        "local_row_sha256": ROW_DIGEST,
        "transfer_bytes": remote.transferred,
        "range_requests": remote.requests,
        "transfer_budget_bytes": remote.budget,
        "full_row_bytes_reconstructed": False,
        "independent_authorization_labels": False,
        "recorded_tools_executed": False,
        **result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-row", type=Path, required=True, help="Private cached row under Git-ignored artifacts/")
    args = parser.parse_args()
    try:
        import pyarrow.parquet as pq  # Optional: research only, not a package dependency.
        result = run_audit(args.local_row, pq=pq)
    except Exception as exc:
        # Do not emit sensitive source messages or arguments in diagnostics.
        print(json.dumps({"status": "NOT_VERIFIED", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
