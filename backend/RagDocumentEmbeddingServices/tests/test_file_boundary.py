from asyncio import run
from io import BytesIO
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from starlette import formparsers

from app.application.documents.use_cases.extract_document_content import ExtractDocumentContent
from app.application.documents.use_cases.upload_document import UploadDocument
from app.infrastructure.extractors.docx_extractor import DocxExtractor
from app.infrastructure.extractors.image_ocr_extractor import ImageOcrExtractor
from app.infrastructure.extractors.pdf_extractor import PdfExtractor
from app.infrastructure.extractors.plain_text_extractor import PlainTextExtractor
from app.infrastructure.storage import document_storage
from app.infrastructure.storage.document_path_resolver import LocalDocumentPathResolver
from app.infrastructure.storage.document_storage import LocalDocumentStorage
from app.interfaces.api import upload_limits
from app.interfaces.api.v1.form_utils import parse_metadata
from app.main import app
from app.shared.errors import ExtractionError, PayloadTooLarge, ValidationError


@pytest.mark.parametrize("declared", [True, False])
def test_http_limit_before_ingestion(monkeypatch, declared):
    monkeypatch.setattr(upload_limits, "MAX_UPLOAD_BODY_BYTES", 200)
    opened = []
    make_file = formparsers.SpooledTemporaryFile

    def track_file(*args, **kwargs):
        file = make_file(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", track_file)
    headers = [(b"content-type", b"multipart/form-data; boundary=fixture")]
    if declared:
        headers.append((b"content-length", b"300"))
    scope = {
        "type": "http", "method": "POST", "path": "/api/v1/documents/upload",
        "root_path": "", "headers": headers, "query_string": b"",
    }
    parts = iter([
        {"type": "http.request", "body": (
            b'--fixture\r\nContent-Disposition: form-data; name="file"; filename="x.txt"\r\n\r\n'
            b"synthetic"
        ), "more_body": True},
        {"type": "http.request", "body": b"x" * 200, "more_body": False},
    ])
    sent = []

    async def receive():
        return next(parts)

    async def send(message):
        sent.append(message)

    run(app(scope, receive, send))
    assert sent[0]["status"] == 413
    assert len(opened) == (0 if declared else 1)
    assert all(file.closed for file in opened)


def test_storage_limits_and_cleans_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(document_storage, "MAX_DOCUMENT_BYTES", 5)
    storage = LocalDocumentStorage(str(tmp_path))
    with pytest.raises(PayloadTooLarge):
        storage.save("fixture.txt", BytesIO(b"123456"))
    assert list(tmp_path.iterdir()) == []
    path, size = storage.save("fixture.txt", BytesIO(b"12345"))
    assert size == 5
    assert (tmp_path / path).read_bytes() == b"12345"


def test_metadata_size_counts_utf8_bytes():
    assert parse_metadata('{"source":"google_drive"}') == {"source": "google_drive"}
    with pytest.raises(PayloadTooLarge):
        parse_metadata('{"text":"' + "é" * 32768 + '"}')


def test_registration_failure_removes_file_but_extraction_failure_keeps_it(tmp_path):
    storage = LocalDocumentStorage(str(tmp_path))
    writer = Mock()
    ingestion = Mock()
    upload = UploadDocument(writer, storage, ingestion)
    writer.create.side_effect = RuntimeError("Synthetic database failure")
    with pytest.raises(RuntimeError, match="database"):
        upload.execute("fixture.txt", "text/plain", BytesIO(b"fixture"))
    assert list(tmp_path.iterdir()) == []

    writer.create.side_effect = None
    ingestion.execute.side_effect = ExtractionError("Synthetic extraction failure")
    with pytest.raises(ExtractionError):
        upload.execute("fixture.txt", "text/plain", BytesIO(b"fixture"))
    stored = list(tmp_path.iterdir())
    assert len(stored) == 1
    assert stored[0].read_bytes() == b"fixture"


def test_storage_resolver_confines_legacy_paths_and_symlinks(tmp_path):
    base = tmp_path / "documents"
    base.mkdir()
    valid = base / "fixture with space.txt"
    valid.write_text("synthetic")
    outside = tmp_path / "outside.txt"
    outside.write_text("synthetic outside")
    (base / "link.txt").symlink_to(outside)
    resolver = LocalDocumentPathResolver(str(base))
    for path in (valid.name, str(valid), valid.as_uri()):
        assert resolver.resolve(path) == str(valid)
    for path in ("../outside.txt", str(outside), outside.as_uri(), "link.txt", "https://outside.example/file.txt"):
        with pytest.raises(ValidationError):
            resolver.resolve(path)


def test_extraction_bounds(tmp_path):
    document = tmp_path / "fixture.txt"
    document.write_text("synthetic")
    extractor = ExtractDocumentContent([PlainTextExtractor()])
    assert extractor.execute(str(document), "text/plain") == "synthetic"
    document.write_text("x" * 1_000_001)
    with pytest.raises(ExtractionError, match="text limit"):
        extractor.execute(str(document), "text/plain")

    archive = tmp_path / "fixture.docx"
    with ZipFile(archive, "w") as file:
        for index in range(1025):
            file.writestr(str(index), b"")
    with pytest.raises(ExtractionError, match="expansion"):
        DocxExtractor().extract(str(archive))

    from pypdf import PdfWriter

    pdf = tmp_path / "fixture.pdf"
    writer = PdfWriter()
    for _ in range(201):
        writer.add_blank_page(72, 72)
    writer.write(pdf)
    with pytest.raises(ExtractionError, match="200-page"):
        PdfExtractor().extract(str(pdf))


def test_ocr_rejects_oversized_image_and_sets_timeout(tmp_path, monkeypatch):
    from PIL import Image

    path = tmp_path / "fixture.png"
    Image.new("1", (4001, 4000)).save(path)
    ocr = Mock(return_value="synthetic")
    monkeypatch.setattr("app.infrastructure.extractors.image_ocr_extractor.pytesseract.image_to_string", ocr)
    with pytest.raises(ExtractionError, match="OCR limit"):
        ImageOcrExtractor().extract(str(path))
    ocr.assert_not_called()
    Image.new("1", (10, 10)).save(path)
    assert ImageOcrExtractor().extract(str(path)) == "synthetic"
    assert ocr.call_args.kwargs["timeout"] == 20
