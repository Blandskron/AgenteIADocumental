"""Safe anti-zip-bomb Office extractors (XLSX via openpyxl, PPTX via python-pptx — MIT) (EVO-008)."""

from __future__ import annotations

from typing import Any
from zipfile import BadZipFile, ZipFile

from app.shared.constants import MAX_EXTRACTED_CHARACTERS
from app.shared.errors import ExtractionError
from app.shared.utils import normalize_text

MAX_ARCHIVE_ENTRIES = 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_XLSX_ROWS_PER_SHEET = 5000
MAX_XLSX_COLS = 50


def _validate_zip_archive(file_path: str, label: str) -> None:
    try:
        with ZipFile(file_path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES or sum(e.file_size for e in entries) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ExtractionError(f"{label} exceeds the archive expansion limit.")
    except BadZipFile as exc:
        raise ExtractionError(f"Invalid {label} archive.") from exc


def _render_md_table(rows: list[list[Any]]) -> str:
    cleaned = [
        [str(cell if cell is not None else "").replace("\n", " ").replace("|", "\\|").strip() for cell in row]
        for row in rows
        if row and any(str(cell if cell is not None else "").strip() for cell in row)
    ]
    if not cleaned:
        return ""
    col_count = max(len(r) for r in cleaned)
    padded = [r + [""] * (col_count - len(r)) for r in cleaned]
    header = "| " + " | ".join(padded[0]) + " |"
    sep = "| " + " | ".join("---" for _ in range(col_count)) + " |"
    body = ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return "\n".join([header, sep, *body])


class XlsxExtractor:
    supported_mime_types = {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

    def extract(self, file_path: str) -> str:
        _validate_zip_archive(file_path, "XLSX")
        try:
            import openpyxl  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ExtractionError("openpyxl is not installed for XLSX extraction.") from exc

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        sections: list[str] = []
        total_chars = 0
        try:
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows: list[list[Any]] = []
                for idx, row in enumerate(ws.iter_rows(values_only=True)):
                    if idx >= MAX_XLSX_ROWS_PER_SHEET:
                        break
                    rows.append(list(row[:MAX_XLSX_COLS]))
                md_table = _render_md_table(rows)
                if md_table:
                    block = f"## Hoja: {sheet_name}\n\n{md_table}"
                    total_chars += len(block)
                    if total_chars > MAX_EXTRACTED_CHARACTERS:
                        raise ExtractionError("XLSX exceeds the extracted text limit.")
                    sections.append(block)
        finally:
            wb.close()
        return normalize_text("\n\n".join(sections))


class PptxExtractor:
    supported_mime_types = {"application/vnd.openxmlformats-officedocument.presentationml.presentation"}

    def extract(self, file_path: str) -> str:
        _validate_zip_archive(file_path, "PPTX")
        try:
            from pptx import Presentation  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ExtractionError("python-pptx is not installed for PPTX extraction.") from exc

        prs = Presentation(file_path)
        slides_text: list[str] = []
        total_chars = 0
        for slide_idx, slide in enumerate(prs.slides, start=1):
            parts: list[str] = [f"[page {slide_idx}]\n## Diapositiva {slide_idx}"]
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False) and shape.text_frame is not None:
                    text = shape.text_frame.text.strip()
                    if text:
                        parts.append(text)
                if getattr(shape, "has_table", False) and shape.table is not None:
                    table_rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
                    md = _render_md_table(table_rows)
                    if md:
                        parts.append(md)
            if getattr(slide, "has_notes_slide", False) and slide.notes_slide is not None:
                notes_frame = getattr(slide.notes_slide, "notes_text_frame", None)
                if notes_frame is not None and notes_frame.text.strip():
                    parts.append(f"Notas: {notes_frame.text.strip()}")
            if len(parts) > 1:
                block = "\n\n".join(parts)
                total_chars += len(block)
                if total_chars > MAX_EXTRACTED_CHARACTERS:
                    raise ExtractionError("PPTX exceeds the extracted text limit.")
                slides_text.append(block)
        return normalize_text("\n\n".join(slides_text))
