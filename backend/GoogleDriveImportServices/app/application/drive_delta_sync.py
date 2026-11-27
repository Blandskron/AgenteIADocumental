"""Incremental delta detector for Google Drive imports using modified_time and md5Checksum (EVO-017)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DriveDeltaResult:
    to_import: list[dict[str, Any]]
    unchanged_ids: list[str]


def detect_drive_deltas(
    remote_files: list[dict[str, Any]],
    existing_by_file_id: dict[str, dict[str, Any]],
) -> DriveDeltaResult:
    """Returns only new or changed Drive files based on md5Checksum / modifiedTime."""
    to_import: list[dict[str, Any]] = []
    unchanged_ids: list[str] = []

    for item in remote_files:
        file_id = str(item.get("id") or item.get("file_id") or "").strip()
        if not file_id:
            continue
        prev = existing_by_file_id.get(file_id)
        if prev is None:
            to_import.append(item)
            continue

        remote_md5 = str(item.get("md5Checksum") or item.get("md5_checksum") or "").strip()
        prev_md5 = str(prev.get("md5_checksum") or "").strip()
        remote_mtime = str(item.get("modifiedTime") or item.get("modified_time") or "").strip()
        prev_mtime = str(prev.get("modified_time") or "").strip()

        if (remote_md5 and prev_md5 and remote_md5 == prev_md5) or (
            not remote_md5 and remote_mtime and prev_mtime and remote_mtime == prev_mtime
        ):
            unchanged_ids.append(file_id)
        else:
            to_import.append(item)

    return DriveDeltaResult(to_import=to_import, unchanged_ids=unchanged_ids)
