from dataclasses import dataclass, field
import hashlib
import io
from pathlib import Path
from typing import Any
from uuid import uuid4
import zipfile

from app.application.documents.use_cases.upload_document import UploadDocument
from app.infrastructure.extractors.markdown_normalizer import is_ignored_vault_path

MAX_BATCH_FILES = 100
MAX_ZIP_UNCOMPRESSED_BYTES = 20 * 1024 * 1024  # 20 MiB
MAX_ZIP_COMPRESSION_RATIO = 50.0
ALLOWED_BATCH_EXTENSIONS = {".md", ".markdown", ".txt"}


@dataclass(frozen=True)
class BatchItemResult:
    path_rel: str
    status: str  # "created" | "reused" | "rejected"
    document_id: str | None = None
    reason: str | None = None


@dataclass
class BatchImportSummary:
    batch_id: str
    created: int = 0
    reused: int = 0
    rejected: int = 0
    items: list[BatchItemResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "created": self.created,
            "reused": self.reused,
            "rejected": self.rejected,
            "items": [
                {
                    "path_rel": item.path_rel,
                    "status": item.status,
                    "document_id": item.document_id,
                    "reason": item.reason,
                }
                for item in self.items
            ],
        }


def _is_unsafe_archive_path(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        return True
    parts = Path(normalized).parts
    return any(part in ("..", "") for part in parts)


def _is_symlink_info(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


class ImportMarkdownBatch:
    def __init__(self, upload_document: UploadDocument) -> None:
        self._upload = upload_document

    def execute_zip(
        self,
        zip_bytes: bytes,
        base_metadata: dict[str, Any],
        process: bool = True,
    ) -> BatchImportSummary:
        batch_id = f"batch-{uuid4().hex[:12]}"
        summary = BatchImportSummary(batch_id=batch_id)

        try:
            archive = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        except zipfile.BadZipFile:
            summary.rejected += 1
            summary.items.append(BatchItemResult(path_rel="<archive>", status="rejected", reason="INVALID_ZIP"))
            return summary

        total_uncompressed = 0
        file_count = 0
        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if is_ignored_vault_path(name):
                    continue
                if _is_unsafe_archive_path(name):
                    summary.rejected += 1
                    summary.items.append(BatchItemResult(path_rel=name, status="rejected", reason="PATH_TRAVERSAL"))
                    continue
                if _is_symlink_info(info):
                    summary.rejected += 1
                    summary.items.append(BatchItemResult(path_rel=name, status="rejected", reason="SYMLINK_REJECTED"))
                    continue

                file_count += 1
                if file_count > MAX_BATCH_FILES:
                    summary.rejected += 1
                    summary.items.append(BatchItemResult(path_rel=name, status="rejected", reason="MAX_FILES_EXCEEDED"))
                    continue

                compressed = max(1, info.compress_size)
                ratio = info.file_size / compressed
                if info.file_size > 16 * 1024 and ratio > MAX_ZIP_COMPRESSION_RATIO:
                    summary.rejected += 1
                    summary.items.append(BatchItemResult(path_rel=name, status="rejected", reason="ZIP_BOMB_RATIO"))
                    continue

                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                    summary.rejected += 1
                    summary.items.append(BatchItemResult(path_rel=name, status="rejected", reason="ZIP_BOMB_SIZE"))
                    continue

                ext = Path(name).suffix.lower()
                if ext not in ALLOWED_BATCH_EXTENSIONS:
                    summary.rejected += 1
                    summary.items.append(BatchItemResult(path_rel=name, status="rejected", reason="UNSUPPORTED_EXTENSION"))
                    continue

                raw_content = archive.read(info)
                self._ingest_single(
                    summary=summary,
                    path_rel=name,
                    raw_content=raw_content,
                    base_metadata=base_metadata,
                    imported_via="zip_batch",
                    process=process,
                )

        return summary

    def execute_files(
        self,
        entries: list[tuple[str, bytes]],
        base_metadata: dict[str, Any],
        process: bool = True,
    ) -> BatchImportSummary:
        batch_id = f"batch-{uuid4().hex[:12]}"
        summary = BatchImportSummary(batch_id=batch_id)
        for index, (path_rel, raw_content) in enumerate(entries, start=1):
            if is_ignored_vault_path(path_rel):
                continue
            if _is_unsafe_archive_path(path_rel):
                summary.rejected += 1
                summary.items.append(BatchItemResult(path_rel=path_rel, status="rejected", reason="PATH_TRAVERSAL"))
                continue
            if index > MAX_BATCH_FILES:
                summary.rejected += 1
                summary.items.append(BatchItemResult(path_rel=path_rel, status="rejected", reason="MAX_FILES_EXCEEDED"))
                continue
            ext = Path(path_rel).suffix.lower()
            if ext not in ALLOWED_BATCH_EXTENSIONS:
                summary.rejected += 1
                summary.items.append(BatchItemResult(path_rel=path_rel, status="rejected", reason="UNSUPPORTED_EXTENSION"))
                continue
            self._ingest_single(
                summary=summary,
                path_rel=path_rel,
                raw_content=raw_content,
                base_metadata=base_metadata,
                imported_via="markdown_batch",
                process=process,
            )
        return summary

    def _ingest_single(
        self,
        summary: BatchImportSummary,
        path_rel: str,
        raw_content: bytes,
        base_metadata: dict[str, Any],
        imported_via: str,
        process: bool,
    ) -> None:
        sha256 = hashlib.sha256(raw_content).hexdigest()
        idempotency_key = f"sha256:{sha256}"
        finder = getattr(self._upload._document_writer, "find_existing_idempotent", None)
        existing = (
            finder(
                owner_user_id=base_metadata.get("owner_user_id"),
                tenant_id=base_metadata.get("tenant_id"),
                idempotency_key=idempotency_key,
                content_sha256=sha256,
            )
            if callable(finder)
            else None
        )
        if existing is not None:
            summary.reused += 1
            summary.items.append(
                BatchItemResult(path_rel=path_rel, status="reused", document_id=existing.document_id)
            )
            return

        mime_type = "text/markdown" if Path(path_rel).suffix.lower() in {".md", ".markdown"} else "text/plain"
        meta = {
            **base_metadata,
            "source": {
                "kind": "markdown_batch",
                "path_rel": path_rel,
                "sha256": sha256,
                "imported_via": imported_via,
                "batch_id": summary.batch_id,
            },
        }
        doc = self._upload.execute(
            filename=Path(path_rel).name,
            mime_type=mime_type,
            file=io.BytesIO(raw_content),
            metadata=meta,
            process=process,
            idempotency_key=idempotency_key,
        )
        summary.created += 1
        summary.items.append(BatchItemResult(path_rel=path_rel, status="created", document_id=doc.document_id))
