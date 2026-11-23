"""Read-only local folder SHA-256 incremental synchronizer with symlink & traversal protection (EVO-017)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

ALLOWED_SYNC_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".tiff"})
MAX_SYNC_FILE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class SyncFileEntry:
    rel_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SyncPlan:
    added: list[SyncFileEntry]
    modified: list[SyncFileEntry]
    unchanged: list[str]
    removed: list[str]
    skipped_unsafe: list[str]


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def scan_local_folder_delta(
    root_dir: Path,
    existing_index: dict[str, str],
    *,
    confirm_deletes: bool = False,
) -> SyncPlan:
    """Scans a local directory read-only and computes added/modified/unchanged/removed files by SHA-256."""
    resolved_root = root_dir.resolve()
    if not resolved_root.is_dir():
        raise ValueError(f"Sync root is not a valid directory: {root_dir}")

    added: list[SyncFileEntry] = []
    modified: list[SyncFileEntry] = []
    unchanged: list[str] = []
    skipped_unsafe: list[str] = []
    seen_paths: set[str] = set()

    for path in sorted(resolved_root.rglob("*")):
        if path.is_symlink():
            skipped_unsafe.append(str(path.name))
            continue
        if not path.is_file():
            continue
        try:
            resolved_file = path.resolve(strict=True)
            rel = resolved_file.relative_to(resolved_root).as_posix()
        except ValueError:
            skipped_unsafe.append(str(path.name))
            continue

        if resolved_file.suffix.lower() not in ALLOWED_SYNC_EXTENSIONS:
            continue
        size = resolved_file.stat().st_size
        if size > MAX_SYNC_FILE_BYTES:
            skipped_unsafe.append(rel)
            continue

        seen_paths.add(rel)
        digest = _sha256_path(resolved_file)
        prev_sha = existing_index.get(rel)
        if prev_sha is None:
            added.append(SyncFileEntry(rel_path=rel, sha256=digest, size_bytes=size))
        elif prev_sha == digest:
            unchanged.append(rel)
        else:
            modified.append(SyncFileEntry(rel_path=rel, sha256=digest, size_bytes=size))

    removed = sorted(set(existing_index) - seen_paths) if confirm_deletes else []
    return SyncPlan(
        added=added,
        modified=modified,
        unchanged=unchanged,
        removed=removed,
        skipped_unsafe=skipped_unsafe,
    )
