from pathlib import Path

from app.shared.utils import normalize_text


class PlainTextExtractor:
    supported_mime_types = {"text/plain", "text/markdown", "text/csv"}

    def extract(self, file_path: str) -> str:
        path = Path(file_path)
        for encoding in ("utf-8", "latin-1"):
            try:
                return normalize_text(path.read_text(encoding=encoding))
            except UnicodeDecodeError:
                continue
        return normalize_text(path.read_text(errors="ignore"))
