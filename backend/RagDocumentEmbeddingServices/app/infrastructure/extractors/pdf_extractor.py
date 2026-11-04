from pypdf import PdfReader

from app.shared.utils import normalize_text


class PdfExtractor:
    supported_mime_types = {"application/pdf"}

    def extract(self, file_path: str) -> str:
        reader = PdfReader(file_path)
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[page {index}]\n{text}")
        return normalize_text("\n\n".join(pages))
