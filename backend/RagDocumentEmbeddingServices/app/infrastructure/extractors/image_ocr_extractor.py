from PIL import Image
import pytesseract

from app.shared.errors import ExtractionError
from app.shared.utils import normalize_text


class ImageOcrExtractor:
    supported_mime_types = {"image/png", "image/jpeg", "image/tiff"}

    def extract(self, file_path: str) -> str:
        try:
            with Image.open(file_path, formats=["PNG", "JPEG", "TIFF"]) as image:
                if image.width * image.height > 16_000_000:
                    raise ExtractionError("Image exceeds the 16 megapixel OCR limit.")
                return normalize_text(pytesseract.image_to_string(image, timeout=20))
        except (OSError, RuntimeError, Image.DecompressionBombError) as exc:
            raise ExtractionError("Image could not be read or OCR did not complete.") from exc
