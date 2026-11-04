import json

import httpx

from app.config.settings import Settings
from app.shared.errors import ExternalServiceError


class DocumentUploadClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.rag_document_base_url.rstrip("/")
        self._timeout = settings.request_timeout_seconds

    def upload(self, bearer_token: str, filename: str, mime_type: str, content: bytes, metadata: dict) -> dict:
        files = {"file": (filename, content, mime_type)}
        data = {"process": "true", "metadata": json.dumps(metadata)}
        headers = {"Authorization": f"Bearer {bearer_token}"}

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(f"{self._base_url}/api/v1/documents/upload", files=files, data=data, headers=headers)

        if response.status_code >= 400:
            raise ExternalServiceError(f"Document upload failed: HTTP {response.status_code} {response.text[:180]}")

        return response.json()
