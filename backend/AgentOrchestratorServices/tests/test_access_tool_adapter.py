from __future__ import annotations

import pytest

from app.application.tools.registry import ToolRegistry
from app.infrastructure.access.access_client import (
    DocumentAccessHttpClient,
    register_document_access_tools,
)


def test_document_access_adapter_fetches_metadata_readonly_with_jwt() -> None:
    captured: list[dict] = []

    def fake_transport(url, headers, _timeout):
        captured.append({"url": url, "headers": headers})
        return {
            "document_id": "doc-acc-1",
            "filename": "contrato_servicios.pdf",
            "status": "PROCESSED",
            "mime_type": "application/pdf",
            "owner_user_id": "u-10",
        }

    registry = ToolRegistry()
    register_document_access_tools(
        registry,
        DocumentAccessHttpClient("http://document-access-service:8000", transport=fake_transport),
    )

    user = {"user_id": "u-10", "active_tenant_id": "t-1", "raw_token": "synthetic.jwt.acc"}
    meta = registry.invoke("get_document_metadata", {"document_id": "doc-acc-1"}, user)
    assert meta["filename"] == "contrato_servicios.pdf"
    assert meta["mime_type"] == "application/pdf"
    assert captured[0]["headers"]["Authorization"] == "Bearer synthetic.jwt.acc"
    assert captured[0]["url"].endswith("/api/v1/documents/doc-acc-1/metadata")

    with pytest.raises(ValueError, match="missing required argument"):
        registry.invoke("get_document_metadata", {}, user)
