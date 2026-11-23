"""Tests for EVO-006: Spanish OCR default (spa+eng) and scanned PDF OCR fallback."""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from app.infrastructure.extractors import image_ocr_extractor, pdf_extractor


def test_run_tesseract_ocr_prefers_spa_eng_and_falls_back_to_eng(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_image_to_string(_img, lang="", timeout=20):
        calls.append(lang)
        if lang == "spa+eng":
            raise image_ocr_extractor.pytesseract.TesseractError(1, "Error opening data file spa.traineddata")
        return "Texto extraido"

    monkeypatch.delenv("TESSERACT_LANG", raising=False)
    monkeypatch.setattr(image_ocr_extractor.pytesseract, "image_to_string", fake_image_to_string)

    out = image_ocr_extractor.run_tesseract_ocr(object())  # type: ignore[arg-type]
    assert out == "Texto extraido"
    assert calls == ["spa+eng", "eng"]


def test_pdf_extractor_uses_ocr_fallback_for_scanned_pages_and_respects_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "")])
    monkeypatch.setattr(pdf_extractor, "PdfReader", lambda _path: fake_reader)
    monkeypatch.setattr(pdf_extractor, "_extract_pdf_tables_by_page", lambda _path: {})
    monkeypatch.setattr(pdf_extractor, "_ocr_pdf_page", lambda _path, idx: f"Cláusula española página {idx + 1} con ñ")

    monkeypatch.setenv("PDF_OCR_FALLBACK_ENABLED", "true")
    extracted = pdf_extractor.PdfExtractor().extract("scanned.pdf")
    assert "[page 1]" in extracted
    assert "Cláusula española página 1 con ñ" in extracted

    monkeypatch.setenv("PDF_OCR_FALLBACK_ENABLED", "false")
    disabled_extracted = pdf_extractor.PdfExtractor().extract("scanned.pdf")
    assert disabled_extracted == ""
