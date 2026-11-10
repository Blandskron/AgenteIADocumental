import json
from time import monotonic

import httpx
import pytest

from app.infrastructure.documents.document_upload_client import DocumentUploadClient
from app.infrastructure.google.bounded_transport import TransferBudget
from app.infrastructure.google.drive_client import GoogleDriveClient
from app.shared.errors import ExternalServiceError, GoogleDriveError, ValidationError
from app.shared.import_limits import MAX_FILE_BYTES


class Chunks(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks, self.closed = chunks, False

    def __iter__(self):
        yield from self.chunks

    def close(self):
        self.closed = True


def mocked_transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


def wire_json(value, status=200):
    return httpx.Response(
        status,
        headers={"content-type": "application/json"},
        stream=Chunks([json.dumps(value).encode()]),
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"content-length": "2"},
        {"content-length": str(MAX_FILE_BYTES + 1)},
        {"content-length": "-1"},
        {"content-encoding": "gzip"},
    ],
)
def test_binary_limit_counts_real_bytes_and_closes_stream(
    settings, monkeypatch, headers
):
    stream = Chunks([b"123", b"456"])

    def handle(request):
        if "alt=media" not in str(request.url):
            return wire_json(
                {"id": "synthetic", "name": "example.txt", "mimeType": "text/plain"}
            )
        return httpx.Response(200, headers=headers, stream=stream)

    mocked_transport(monkeypatch, handle)
    with pytest.raises(GoogleDriveError):
        GoogleDriveClient(settings).download_file("synthetic", "synthetic", maximum=5)
    assert stream.closed


def test_exact_boundary_spills_to_disk_and_closes_explicitly(settings, monkeypatch):
    stream = Chunks([b"a" * 65536 for _ in range(MAX_FILE_BYTES // 65536)])

    def handle(request):
        return (
            httpx.Response(200, stream=stream)
            if "alt=media" in str(request.url)
            else wire_json(
                {"id": "synthetic", "name": "file.txt", "mimeType": "text/plain"}
            )
        )

    mocked_transport(monkeypatch, handle)
    download = GoogleDriveClient(settings).download_file("synthetic", "synthetic")
    assert download.size_bytes == MAX_FILE_BYTES and download.content._rolled
    assert download.content.read(3) == b"aaa"
    download.close()
    assert download.content.closed and stream.closed


@pytest.mark.parametrize(
    "native", ["document", "spreadsheet", "presentation", "drawing"]
)
def test_native_export_uses_supported_ingestion_format(settings, monkeypatch, native):
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/export"):
            expected = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if native == "document"
                else "application/pdf"
            )
            assert request.url.params["mimeType"] == expected
            return httpx.Response(200, stream=Chunks([b"synthetic-binary"]))
        return wire_json(
            {
                "id": "synthetic",
                "name": "example",
                "mimeType": "application/vnd.google-apps." + native,
            }
        )

    mocked_transport(monkeypatch, handle)
    download = GoogleDriveClient(settings).download_file("synthetic", "synthetic")
    assert download.filename.endswith(".docx" if native == "document" else ".pdf")
    download.close()
    assert len(seen) == 2


@pytest.mark.parametrize(
    "metadata",
    [
        {"id": "other", "name": "file", "mimeType": "text/plain"},
        {"id": "synthetic", "name": "../private", "mimeType": "text/plain"},
        {
            "id": "synthetic",
            "name": "file",
            "mimeType": "application/vnd.google-apps.shortcut",
        },
        {
            "id": "synthetic",
            "name": "file.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
        {
            "id": "synthetic",
            "name": "file",
            "mimeType": "text/plain",
            "size": str(MAX_FILE_BYTES + 1),
        },
        {"id": "synthetic", "name": "file", "mimeType": "text/plain", "size": "-1"},
    ],
)
def test_bad_metadata_is_rejected_before_media(settings, monkeypatch, metadata):
    calls = []

    def handle(request):
        calls.append(request)
        return wire_json(metadata)

    mocked_transport(monkeypatch, handle)
    with pytest.raises((GoogleDriveError, ValidationError)):
        GoogleDriveClient(settings).download_file("synthetic", "synthetic")
    assert len(calls) == 1


def test_byte_budget_survives_failed_download_and_deadline_is_checked_per_chunk(
    settings, monkeypatch
):
    budget = TransferBudget(5)

    def handle(request):
        if "alt=media" in str(request.url):
            return httpx.Response(200, stream=Chunks([b"123", b"456"]))
        return wire_json(
            {"id": "synthetic", "name": "file.txt", "mimeType": "text/plain"}
        )

    mocked_transport(monkeypatch, handle)
    with pytest.raises(GoogleDriveError):
        GoogleDriveClient(settings).download_file(
            "synthetic", "synthetic", budget=budget
        )
    assert budget.remaining == 0
    with pytest.raises(GoogleDriveError):
        GoogleDriveClient(settings).download_file(
            "synthetic", "synthetic", deadline=monotonic() - 1
        )


@pytest.mark.parametrize(
    "response",
    [
        [],
        {"document_id": "../secret", "status": "PROCESSED"},
        {"document_id": "synthetic", "status": "unexpected"},
        {"status": "PROCESSED"},
    ],
)
def test_upload_unknown_responses_are_sanitized(settings, monkeypatch, response):
    mocked_transport(monkeypatch, lambda request: wire_json(response))
    with pytest.raises(ExternalServiceError, match="requires review"):
        DocumentUploadClient(settings).upload(
            "synthetic", "file.txt", "text/plain", b"synthetic", {}
        )


@pytest.mark.parametrize(
    "identifier", ["../private", "a/b", "a?alt=media", "a#fragment", "a" * 257]
)
def test_invalid_ids_never_contact_google(settings, identifier):
    with pytest.raises(ValidationError):
        GoogleDriveClient(settings).get_file_metadata("synthetic", identifier)


@pytest.mark.parametrize("status", [401, 403])
def test_ingestion_authorization_rejection_is_known_before_creation(
    settings, monkeypatch, status
):
    from app.shared.errors import UploadRejected

    mocked_transport(
        monkeypatch,
        lambda request: wire_json({"detail": "synthetic rejection"}, status),
    )
    with pytest.raises(UploadRejected):
        DocumentUploadClient(settings).upload(
            "synthetic", "file.txt", "text/plain", b"synthetic", {}
        )


def test_upload_and_processing_are_separate_bounded_requests(settings, monkeypatch):
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/upload"):
            assert b"\r\nfalse\r\n" in request.content
            return wire_json({"document_id": "synthetic", "status": "PENDING"})
        assert request.url.path.endswith("/synthetic/process")
        return wire_json({"document_id": "synthetic", "status": "PROCESSED"})

    mocked_transport(monkeypatch, handle)
    client = DocumentUploadClient(settings)
    assert (
        client.upload("synthetic", "file.txt", "text/plain", b"synthetic", {})[
            "document_id"
        ]
        == "synthetic"
    )
    assert client.process_document("synthetic", "synthetic")["status"] == "PROCESSED"
    assert len(seen) == 2


@pytest.mark.parametrize(
    "code", ["document_relation_changed", "unknown", None, [], {"private": "value"}]
)
def test_only_explicit_creation_rollback_is_a_safe_rejection(
    settings, monkeypatch, code
):
    from app.shared.errors import UploadRejected

    mocked_transport(monkeypatch, lambda request: wire_json({"code": code}, 409))
    with pytest.raises(ExternalServiceError) as error:
        DocumentUploadClient(settings).upload(
            "synthetic", "file.txt", "text/plain", b"synthetic", {}
        )
    assert isinstance(error.value, UploadRejected) == (
        code == "document_relation_changed"
    )


@pytest.mark.parametrize(
    "headers,body",
    [
        ({}, b"invalid-json"),
        ({}, b"x" * 32769),
        ({"content-encoding": "gzip"}, b'{"code":"document_relation_changed"}'),
        ({"content-length": "1"}, b'{"code":"document_relation_changed"}'),
    ],
)
def test_malformed_rejection_is_uncertain_and_closes_body(
    settings, monkeypatch, headers, body
):
    from app.shared.errors import UploadRejected

    stream = Chunks([body])
    mocked_transport(
        monkeypatch, lambda request: httpx.Response(409, headers=headers, stream=stream)
    )
    with pytest.raises(ExternalServiceError) as error:
        DocumentUploadClient(settings).upload(
            "synthetic", "file.txt", "text/plain", b"synthetic", {}
        )
    assert not isinstance(error.value, UploadRejected)
    assert stream.closed


def test_success_status_cannot_masquerade_as_known_rejection(settings, monkeypatch):
    from app.shared.errors import UploadRejected

    mocked_transport(
        monkeypatch, lambda request: wire_json({"code": "document_relation_changed"})
    )
    with pytest.raises(ExternalServiceError) as error:
        DocumentUploadClient(settings).upload(
            "synthetic", "file.txt", "text/plain", b"synthetic", {}
        )
    assert not isinstance(error.value, UploadRejected)
