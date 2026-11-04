from dataclasses import replace
from typing import BinaryIO

from app.application.documents.ports import DocumentWriter
from app.application.documents.use_cases.ingest_existing_document import IngestExistingDocument
from app.domain.documents import Document, DocumentStatus


class UploadDocument:
    def __init__(
        self,
        document_writer: DocumentWriter,
        storage,
        ingestion: IngestExistingDocument,
    ) -> None:
        self._document_writer = document_writer
        self._storage = storage
        self._ingestion = ingestion

    def execute(
        self,
        filename: str,
        mime_type: str,
        file: BinaryIO,
        metadata: dict | None = None,
        process: bool = True,
    ) -> Document:
        storage_path, size_bytes = self._storage.save(filename, file)
        document_metadata = {
            **(metadata or {}),
            "original_filename": filename,
            "size_bytes": size_bytes,
        }
        document = self._document_writer.create(
            filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            metadata=document_metadata,
            status="PENDING",
        )

        if process:
            self._ingestion.execute(document.document_id)
            return replace(document, status=DocumentStatus.PROCESSED)

        return document
