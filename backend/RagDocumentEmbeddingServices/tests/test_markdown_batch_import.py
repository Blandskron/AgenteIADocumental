import io
import zipfile

from app.application.documents.use_cases.import_markdown_batch import ImportMarkdownBatch
from app.application.documents.use_cases.upload_document import UploadDocument
from app.infrastructure.storage.document_storage import LocalDocumentStorage
from tests.test_idempotency_and_markdown import _InMemoryWriter, _NoOpIngestion


def _build_zip(entries: list[tuple[str, bytes, bool]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data, is_symlink in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if is_symlink:
                info.external_attr = (0o120777 << 16)
            zf.writestr(info, data)
    return buf.getvalue()


def test_zip_batch_import_rejects_malicious_and_deduplicates_on_reimport(tmp_path):
    writer = _InMemoryWriter()
    storage = LocalDocumentStorage(str(tmp_path))
    upload = UploadDocument(writer, storage, _NoOpIngestion())
    importer = ImportMarkdownBatch(upload)

    raw_zip = _build_zip([
        ("vault/nota_a.md", b"# Nota A\n\nContenido sintetico [[Nota-B]].", False),
        (".obsidian/workspace.json", b"{}", False),
        ("../../etc/passwd", b"malicious", False),
        ("vault/link.md", b"target", True),
        ("vault/bomb.md", b"0" * (1024 * 1024), False),
        ("vault/script.exe", b"MZ", False),
    ])
    meta = {"owner_user_id": "42", "tenant_id": "t1"}

    first = importer.execute_zip(raw_zip, base_metadata=meta, process=False)
    assert first.created == 1
    assert first.reused == 0
    assert first.rejected == 4
    reasons = {item.reason for item in first.items if item.status == "rejected"}
    assert reasons == {"PATH_TRAVERSAL", "SYMLINK_REJECTED", "ZIP_BOMB_RATIO", "UNSUPPORTED_EXTENSION"}

    # Re-importing the exact same archive reuses the existing document without creating duplicates.
    second = importer.execute_zip(raw_zip, base_metadata=meta, process=False)
    assert second.created == 0
    assert second.reused == 1
    assert len(writer.docs) == 1
