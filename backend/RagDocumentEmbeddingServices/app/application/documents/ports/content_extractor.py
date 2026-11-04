from typing import Protocol


class DocumentContentExtractor(Protocol):
    supported_mime_types: set[str]

    def extract(self, file_path: str) -> str:
        ...
