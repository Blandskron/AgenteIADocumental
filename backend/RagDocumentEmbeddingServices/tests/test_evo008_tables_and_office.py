"""Tests for EVO-008 (CSV/DOCX/Office table extraction & zip-bomb guard) and EVO-009 (SKIP LOCKED)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest

from app.infrastructure.extractors.office_extractor import PptxExtractor, XlsxExtractor, _validate_zip_archive
from app.infrastructure.extractors.plain_text_extractor import PlainTextExtractor
from app.shared.errors import ExtractionError


def test_csv_extractor_renders_markdown_table(tmp_path: Path) -> None:
    csv_file = tmp_path / "ventas.csv"
    csv_file.write_text("Mes;Ingresos;Moneda\nEnero;12000;USD\nFebrero;15500;USD\n", encoding="utf-8")

    extracted = PlainTextExtractor().extract(str(csv_file))
    assert "| Mes | Ingresos | Moneda |" in extracted
    assert "| --- | --- | --- |" in extracted
    assert "| Enero | 12000 | USD |" in extracted


def test_office_extractors_reject_invalid_zip_archives(tmp_path: Path) -> None:
    bad_file = tmp_path / "corrupt.xlsx"
    bad_file.write_bytes(b"not a zip")

    with pytest.raises(ExtractionError):
        _validate_zip_archive(str(bad_file), "XLSX")

    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in XlsxExtractor.supported_mime_types
    assert (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        in PptxExtractor.supported_mime_types
    )


def test_office_zip_bomb_entry_count_guard(tmp_path: Path) -> None:
    bomb = tmp_path / "many.xlsx"
    with ZipFile(bomb, "w") as zf:
        for i in range(1030):
            zf.writestr(f"f{i}.txt", "x")

    with pytest.raises(ExtractionError, match="archive expansion limit"):
        _validate_zip_archive(str(bomb), "XLSX")


def test_claim_next_pending_document_uses_skip_locked_sql() -> None:
    pytest.importorskip("pydantic_settings")
    from app.interfaces.workers.process_document_worker import claim_next_pending_document

    executed_sql: list[str] = []

    class _Res:
        def mappings(self) -> _Res:
            return self

        def first(self) -> dict[str, Any]:
            return {"document_id": "doc-queued-1"}

    class _Sess:
        def execute(self, stmt: Any) -> _Res:
            executed_sql.append(str(stmt))
            return _Res()

        def commit(self) -> None:
            return None

    doc_id = claim_next_pending_document(_Sess())  # type: ignore[arg-type]
    assert doc_id == "doc-queued-1"
    assert any("FOR UPDATE SKIP LOCKED" in sql for sql in executed_sql)
