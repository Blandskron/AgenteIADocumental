from app.application.documents.ports import DocumentContentExtractor
from app.shared.errors import ExtractionError


class ExtractDocumentContent:
    def __init__(self, extractors: list[DocumentContentExtractor]) -> None:
        self._extractors = extractors

    def execute(self, file_path: str, mime_type: str) -> str:
        for extractor in self._extractors:
            if mime_type in extractor.supported_mime_types:
                return extractor.extract(file_path)
        raise ExtractionError(f"Unsupported document MIME type: {mime_type}")
