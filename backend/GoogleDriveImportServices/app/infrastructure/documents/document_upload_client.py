import json
from time import monotonic


from app.infrastructure.google.bounded_transport import provider_json
from app.shared.errors import ExternalServiceError, ProviderStatusError, UploadRejected
from app.shared.import_limits import FILE_ID


class DocumentUploadClient:
    def __init__(self, settings):
        self._base_url = settings.rag_document_base_url.rstrip("/")
        self._timeout = settings.request_timeout_seconds

    def upload(
        self, bearer_token, filename, mime_type, content, metadata, *, deadline=None
    ):
        deadline = deadline or monotonic() + self._timeout
        try:
            value = provider_json(
                "POST",
                f"{self._base_url}/api/v1/documents/upload",
                timeout=self._timeout,
                deadline=deadline,
                rejection_codes={409: {"document_relation_changed"}},
                files={"file": (filename, content, mime_type)},
                data={
                    "process": "false",
                    "metadata": json.dumps(metadata, allow_nan=False),
                },
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            identifier = value.get("document_id")
            if (
                not isinstance(identifier, str)
                or not FILE_ID.fullmatch(identifier)
                or value.get("status")
                not in {"PROCESSED", "UPLOADED", "PROCESSING", "PENDING", "FAILED"}
            ):
                raise ValueError()
            return {"document_id": identifier, "status": value["status"]}
        except ProviderStatusError as exc:
            if exc.status in {401, 403} or (
                exc.status == 409 and exc.code == "document_relation_changed"
            ):
                raise UploadRejected(
                    "Ingestion rejected the request before document creation."
                ) from None
            raise ExternalServiceError(
                "Document upload outcome requires review."
            ) from None
        except Exception:
            raise ExternalServiceError(
                "Document upload outcome requires review."
            ) from None

    def process_document(self, bearer_token, document_id, *, deadline=None):
        try:
            if not FILE_ID.fullmatch(document_id):
                raise ValueError()
            value = provider_json(
                "POST",
                f"{self._base_url}/api/v1/documents/{document_id}/process",
                timeout=self._timeout,
                deadline=deadline,
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            if (
                value.get("document_id") != document_id
                or value.get("status") != "PROCESSED"
            ):
                raise ValueError()
            return value
        except Exception:
            raise ExternalServiceError(
                "Document processing requires review; the uploaded document is retained."
            ) from None
