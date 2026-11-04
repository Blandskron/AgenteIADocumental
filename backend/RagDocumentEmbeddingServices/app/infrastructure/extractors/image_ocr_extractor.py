from PIL import Image
import pytesseract

from app.shared.utils import normalize_text


class ImageOcrExtractor:
    supported_mime_types = {"image/png", "image/jpeg", "image/tiff"}

    def extract(self, file_path: str) -> str:
        with Image.open(file_path) as image:
            return normalize_text(pytesseract.image_to_string(image))
