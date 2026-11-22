from __future__ import annotations

import pytest

from app.application.tools.registry import ToolRegistry
from app.infrastructure.search.search_client import (
    DocumentSearchHttpClient,
    register_document_search_tools,
)


def test_document_search_adapter_propagates_jwt_and_caps_limit() -> None:
    captured: list[dict] = []

    def fake_transport(url, headers, _timeout):
        captured.append({"url": url, "headers": headers})
        return {
            "items": [
                {
                    "document_id": "doc-fts-1",
                    "filename": "anexo_tarifas.pdf",
                    "status": "PROCESSED",
                    "snippet": "Tarifa base USD 1200 mensual.",
                }
            ],
            "total": 1,
        }

    registry = ToolRegistry()
    client = DocumentSearchHttpClient("http://document-search-service:8000", transport=fake_transport)
    register_document_search_tools(registry, client)

    user = {"user_id": "u-7", "active_tenant_id": "t-1", "raw_token": "synthetic.jwt.fts"}
    result = registry.invoke("search_documents_fts", {"query": "tarifa", "limit": 999}, user)

    assert result["total"] == 1
    assert result["items"][0]["document_id"] == "doc-fts-1"
    assert "limit=20" in captured[0]["url"]
    assert captured[0]["headers"]["Authorization"] == "Bearer synthetic.jwt.fts"

    # Missing required argument raises ValueError
    with pytest.raises(ValueError, match="missing required argument"):
        registry.invoke("search_documents_fts", {}, user)
