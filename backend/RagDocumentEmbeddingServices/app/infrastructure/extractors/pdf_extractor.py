from pypdf import PdfReader

from app.shared.constants import MAX_EXTRACTED_CHARACTERS
from app.shared.errors import ExtractionError
from app.shared.utils import normalize_text


class PdfExtractor:
    supported_mime_types = {"application/pdf"}

    def extract(self, file_path: str) -> str:
        reader = PdfReader(file_path)
        if len(reader.pages) > 200:
            raise ExtractionError("PDF exceeds the 200-page limit.")
        pages = []
        extracted = 0
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            extracted += len(text)
            if extracted > MAX_EXTRACTED_CHARACTERS:
                raise ExtractionError("PDF exceeds the extracted text limit.")
            if text.strip():
                pages.append(f"[page {index}]\n{text}")
        return normalize_text("\n\n".join(pages))
