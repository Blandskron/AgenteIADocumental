from dataclasses import replace
import hashlib
from pathlib import Path
from typing import BinaryIO

from app.application.documents.ports import DocumentWriter
from app.application.documents.use_cases.ingest_existing_document import IngestExistingDocument
from app.domain.documents import Document, DocumentStatus
from app.infrastructure.extractors.markdown_normalizer import normalize_markdown


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


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
        idempotency_key: str | None = None,
    ) -> Document:
        raw_meta = dict(metadata or {})
        clean_key = (idempotency_key or "").strip()[:128] or None
        finder = getattr(self._document_writer, "find_existing_idempotent", None)

        if clean_key and callable(finder):
            existing = finder(
                owner_user_id=raw_meta.get("owner_user_id"),
                tenant_id=raw_meta.get("tenant_id"),
                idempotency_key=clean_key,
            )
            if existing is not None:
                return existing

        storage_path, size_bytes = self._storage.save(filename, file)
        content_sha256 = None
        markdown_meta: dict | None = None
        base_path = getattr(self._storage, "_base_path", None)
        if base_path is not None:
            saved_file = Path(base_path) / storage_path
            if saved_file.is_file():
                content_sha256 = _sha256_file(saved_file)
                if mime_type == "text/markdown" or filename.lower().endswith(".md"):
                    parsed_md = normalize_markdown(saved_file.read_text(encoding="utf-8", errors="ignore"))
                    markdown_meta = {
                        "frontmatter": parsed_md.frontmatter,
                        "wikilinks": parsed_md.wikilinks,
                        "markdown_links": parsed_md.markdown_links,
                        "tags": parsed_md.tags,
                    }

        if clean_key and content_sha256 and callable(finder):
            existing = finder(
                owner_user_id=raw_meta.get("owner_user_id"),
                tenant_id=raw_meta.get("tenant_id"),
                idempotency_key=clean_key,
                content_sha256=content_sha256,
            )
            if existing is not None:
                self._storage.remove(storage_path)
                return existing

        source_meta = dict(raw_meta.get("source")) if isinstance(raw_meta.get("source"), dict) else {}
        source_meta.setdefault("kind", "upload")
        source_meta.setdefault("path_rel", filename)
        source_meta.setdefault("imported_via", "api")
        if content_sha256:
            source_meta["sha256"] = content_sha256

        document_metadata = {
            **raw_meta,
            "original_filename": filename,
            "size_bytes": size_bytes,
            "source": source_meta,
        }
        if content_sha256:
            document_metadata["content_sha256"] = content_sha256
        if clean_key:
            document_metadata["idempotency_key"] = clean_key
        if markdown_meta:
            document_metadata["markdown"] = markdown_meta

        try:
            document = self._document_writer.create(
                filename=filename,
                storage_path=storage_path,
                mime_type=mime_type,
                metadata=document_metadata,
                status="PENDING",
            )
        except Exception:
            self._storage.remove(storage_path)
            raise

        if process:
            self._ingestion.execute(document.document_id)
            return replace(document, status=DocumentStatus.PROCESSED)

        return document
