import os

from PIL import Image
import pytesseract

from app.shared.errors import ExtractionError
from app.shared.utils import normalize_text


def default_ocr_lang() -> str:
    return (os.environ.get("TESSERACT_LANG") or "spa+eng").strip() or "spa+eng"


def run_tesseract_ocr(image: Image.Image, *, lang: str | None = None, timeout: int = 20) -> str:
    """Runs Tesseract OCR preferring spa+eng with automatic fallback to eng if spa tessdata is absent."""
    target_lang = (lang or default_ocr_lang()).strip()
    try:
        return pytesseract.image_to_string(image, lang=target_lang, timeout=timeout)
    except pytesseract.TesseractError as exc:
        if "spa" in target_lang and target_lang != "eng":
            return pytesseract.image_to_string(image, lang="eng", timeout=timeout)
        raise RuntimeError(f"Tesseract OCR failed: {exc}") from exc


class ImageOcrExtractor:
    supported_mime_types = {"image/png", "image/jpeg", "image/tiff"}

    def extract(self, file_path: str) -> str:
        try:
            with Image.open(file_path, formats=["PNG", "JPEG", "TIFF"]) as image:
                if image.width * image.height > 16_000_000:
                    raise ExtractionError("Image exceeds the 16 megapixel OCR limit.")
                return normalize_text(run_tesseract_ocr(image, timeout=20))
        except (OSError, RuntimeError, Image.DecompressionBombError) as exc:
            raise ExtractionError("Image could not be read or OCR did not complete.") from exc
