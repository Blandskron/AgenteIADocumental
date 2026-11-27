"""Tests for EVO-017: local folder SHA-256 delta sync and safe delete guard."""

from __future__ import annotations

from pathlib import Path

from app.application.documents.use_cases.sync_local_folder import scan_local_folder_delta


def test_local_folder_sync_detects_added_unchanged_modified_and_requires_delete_confirm(tmp_path: Path) -> None:
    doc_a = tmp_path / "a.md"
    doc_a.write_text("# Documento A v1", encoding="utf-8")

    # Initial scan -> 1 added
    plan1 = scan_local_folder_delta(tmp_path, {})
    assert [e.rel_path for e in plan1.added] == ["a.md"]
    assert plan1.modified == []
    assert plan1.unchanged == []

    index = {e.rel_path: e.sha256 for e in plan1.added}

    # Re-scan unchanged -> 0 reindexations
    plan2 = scan_local_folder_delta(tmp_path, index)
    assert plan2.added == []
    assert plan2.modified == []
    assert plan2.unchanged == ["a.md"]

    # Modify a.md -> detected as modified
    doc_a.write_text("# Documento A v2 modificado", encoding="utf-8")
    plan3 = scan_local_folder_delta(tmp_path, index)
    assert [e.rel_path for e in plan3.modified] == ["a.md"]

    # Delete a.md -> not removed unless confirm_deletes=True
    doc_a.unlink()
    plan4_safe = scan_local_folder_delta(tmp_path, index, confirm_deletes=False)
    assert plan4_safe.removed == []
    plan4_confirmed = scan_local_folder_delta(tmp_path, index, confirm_deletes=True)
    assert plan4_confirmed.removed == ["a.md"]
