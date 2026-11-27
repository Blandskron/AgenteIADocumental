import os
from typing import Any

from pypdf import PdfReader

from app.infrastructure.extractors.image_ocr_extractor import run_tesseract_ocr
from app.shared.constants import MAX_EXTRACTED_CHARACTERS
from app.shared.errors import ExtractionError
from app.shared.utils import normalize_text

_MIN_TEXT_CHARS_FOR_NO_OCR = 20


def _is_pdf_ocr_fallback_enabled() -> bool:
    return (os.environ.get("PDF_OCR_FALLBACK_ENABLED", "true").strip().lower() not in {"0", "false", "no"})


def _render_markdown_table(rows: list[list[Any]]) -> str:
    cleaned_rows = [
        [str(cell or "").replace("\n", " ").replace("|", "\\|").strip() for cell in row]
        for row in rows
        if row and any(str(cell or "").strip() for cell in row)
    ]
    if not cleaned_rows:
        return ""
    col_count = max(len(row) for row in cleaned_rows)
    padded = [row + [""] * (col_count - len(row)) for row in cleaned_rows]
    header = "| " + " | ".join(padded[0]) + " |"
    sep = "| " + " | ".join("---" for _ in range(col_count)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in padded[1:]]
    return "\n".join([header, sep, *body])


def _extract_pdf_tables_by_page(file_path: str) -> dict[int, list[str]]:
    """Extracts structured Markdown tables per 1-based page using pdfplumber when installed."""
    try:
        import pdfplumber  # type: ignore[import-not-found]
    except ImportError:
        return {}

    tables_by_page: dict[int, list[str]] = {}
    try:
        with pdfplumber.open(file_path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                raw_tables = page.extract_tables() or []
                rendered = [md for tbl in raw_tables if (md := _render_markdown_table(tbl))]
                if rendered:
                    tables_by_page[idx] = rendered
    except Exception:
        return {}
    return tables_by_page


def _ocr_pdf_page(file_path: str, page_index_zero_based: int) -> str:
    """Rasterizes a single PDF page with pypdfium2 and runs Tesseract OCR (spa+eng)."""
    try:
        import pypdfium2 as pdfium  # type: ignore[import-not-found]
    except ImportError:
        return ""

    dpi = max(100, min(300, int(os.environ.get("PDF_OCR_DPI", "180"))))
    scale = dpi / 72.0
    pdf = pdfium.PdfDocument(file_path)
    try:
        page = pdf[page_index_zero_based]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        try:
            if pil_image.width * pil_image.height > 16_000_000:
                return ""
            return run_tesseract_ocr(pil_image, timeout=25)
        finally:
            pil_image.close()
    except Exception:
        return ""
    finally:
        pdf.close()


class PdfExtractor:
    supported_mime_types = {"application/pdf"}

    def extract(self, file_path: str) -> str:
        reader = PdfReader(file_path)
        if len(reader.pages) > 200:
            raise ExtractionError("PDF exceeds the 200-page limit.")

        ocr_enabled = _is_pdf_ocr_fallback_enabled()
        max_ocr_pages = max(1, min(100, int(os.environ.get("PDF_OCR_MAX_PAGES", "30"))))
        ocr_pages_used = 0
        tables_by_page = _extract_pdf_tables_by_page(file_path)

        pages: list[str] = []
        extracted = 0
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if len(text) < _MIN_TEXT_CHARS_FOR_NO_OCR and ocr_enabled and ocr_pages_used < max_ocr_pages:
                ocr_text = _ocr_pdf_page(file_path, index - 1).strip()
                if ocr_text:
                    text = ocr_text
                    ocr_pages_used += 1

            page_tables = tables_by_page.get(index) or []
            parts = [part for part in [text, *page_tables] if part]
            page_body = "\n\n".join(parts)

            extracted += len(page_body)
            if extracted > MAX_EXTRACTED_CHARACTERS:
                raise ExtractionError("PDF exceeds the extracted text limit.")
            if page_body:
                pages.append(f"[page {index}]\n{page_body}")
        return normalize_text("\n\n".join(pages))
