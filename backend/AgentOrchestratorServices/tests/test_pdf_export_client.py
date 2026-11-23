from __future__ import annotations

import uuid
import pytest

from app.infrastructure.export.pdf_export_client import AgentPdfExportClient


def test_pdf_export_client_propagates_jwt_and_falls_back_cleanly() -> None:
    captured: list[dict] = []

    def ok_transport(url, payload, headers, _timeout):
        captured.append({"url": url, "payload": payload, "headers": headers})
        return {"export_id": "exp_999"}

    run = {
        "run_id": "run_pdf1",
        "goal": "Informe legal",
        "result_markdown": "Resumen [Fuente 1].",
        "sources": [{"document_id": "doc-1", "chunk_index": 0, "quote": "Texto"}],
        "provider": "ollama",
        "steps_used": 2,
    }
    client = AgentPdfExportClient("http://document-export-service:8000", transport=ok_transport)
    created = client.export_run_to_pdf(run=run, user_jwt="synthetic.jwt.pdf")
    assert created["status"] == "created"
    assert created["export_id"] == "exp_999"
    assert captured[0]["headers"]["Authorization"] == "Bearer synthetic.jwt.pdf"
    assert captured[0]["url"].endswith("/api/v1/exports/chat-message/pdf")
    assert uuid.UUID(captured[0]["headers"]["Idempotency-Key"]).version == 5

    offline_client = AgentPdfExportClient(
        "http://document-export-service:8000",
        transport=lambda *_a: (_ for _ in ()).throw(ConnectionError("offline")),
    )
    fallback = offline_client.export_run_to_pdf(run=run, user_jwt="synthetic.jwt.pdf")
    assert fallback["status"] == "export_service_unavailable_fallback"
    assert "# Informe Agente Documental — run_pdf1" in fallback["fallback_markdown"]

    with pytest.raises(PermissionError):
        client.export_run_to_pdf(run=run, user_jwt="")
