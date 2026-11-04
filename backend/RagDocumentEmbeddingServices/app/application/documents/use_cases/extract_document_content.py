from pathlib import Path

from app.application.documents.ports import DocumentContentExtractor
from app.shared.constants import MAX_DOCUMENT_BYTES, MAX_EXTRACTED_CHARACTERS
from app.shared.errors import ExtractionError


class ExtractDocumentContent:
    def __init__(self, extractors: list[DocumentContentExtractor]) -> None:
        self._extractors = extractors

    def execute(self, file_path: str, mime_type: str) -> str:
        if Path(file_path).stat().st_size > MAX_DOCUMENT_BYTES:
            raise ExtractionError("Document exceeds the extraction size limit.")
        for extractor in self._extractors:
            if mime_type in extractor.supported_mime_types:
                text = extractor.extract(file_path)
                if len(text) > MAX_EXTRACTED_CHARACTERS:
                    raise ExtractionError("Document exceeds the extracted text limit.")
                return text
        raise ExtractionError(f"Unsupported document MIME type: {mime_type}")
