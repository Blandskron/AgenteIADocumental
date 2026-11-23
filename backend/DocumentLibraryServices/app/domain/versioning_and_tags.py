"""Domain helpers for document versioning, deterministic diffs, tags, and shared folder visibility (EVO-014)."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import os
import re

ALLOWED_FOLDER_VISIBILITIES = frozenset({"private", "area", "company"})
ALLOWED_TAG_COLORS = frozenset({"slate", "blue", "emerald", "amber", "rose", "violet", "cyan"})
_TAG_CLEAN_RE = re.compile(r"\s+")


def max_versions_per_document() -> int:
    return max(1, min(100, int(os.environ.get("MAX_VERSIONS_PER_DOCUMENT", "20"))))


def normalize_tag_name(raw: str) -> str:
    cleaned = _TAG_CLEAN_RE.sub(" ", (raw or "").strip())
    if not cleaned or len(cleaned) > 64:
        raise ValueError("Tag name must be between 1 and 64 characters.")
    return cleaned


def validate_tag_color(color: str | None) -> str:
    candidate = (color or "slate").strip().lower()
    if candidate not in ALLOWED_TAG_COLORS:
        raise ValueError(f"Unsupported tag color: {candidate}")
    return candidate


def validate_folder_visibility(visibility: str, area_id: str | None = None) -> tuple[str, str | None]:
    vis = (visibility or "private").strip().lower()
    if vis not in ALLOWED_FOLDER_VISIBILITIES:
        raise ValueError(f"Unsupported folder visibility: {vis}")
    if vis == "area" and not (area_id or "").strip():
        raise ValueError("Folder visibility='area' requires an explicit area_id.")
    return vis, (area_id.strip() if area_id and vis == "area" else None)


@dataclass(frozen=True)
class VersionDiffSummary:
    added_lines: int
    removed_lines: int
    unified_diff: str
    identical: bool


def compute_version_diff(
    old_text: str,
    new_text: str,
    *,
    from_label: str = "v1",
    to_label: str = "v2",
    max_diff_chars: int = 16_000,
) -> VersionDiffSummary:
    """Computes a deterministic unified diff between two document versions."""
    old_lines = (old_text or "").splitlines()
    new_lines = (new_text or "").splitlines()
    diff_lines = list(
        difflib.unified_diff(old_lines, new_lines, fromfile=from_label, tofile=to_label, lineterm="")
    )
    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    joined = "\n".join(diff_lines)[:max_diff_chars]
    return VersionDiffSummary(
        added_lines=added,
        removed_lines=removed,
        unified_diff=joined,
        identical=(added == 0 and removed == 0),
    )
