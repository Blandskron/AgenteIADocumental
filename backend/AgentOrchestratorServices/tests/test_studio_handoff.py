from __future__ import annotations

import pytest
from app.infrastructure.studio.studio_client import (
    StudioHandoffClient,
    validate_sources_groundedness,
)


def test_studio_handoff_saves_grounded_artifact_with_user_jwt() -> None:
    captured: list[dict] = []

    def fake_transport(url, payload, headers, _timeout):
        captured.append({"url": url, "payload": payload, "headers": headers})
        return {"artifact_id": "art_001", "status": "FRESH"}

    client = StudioHandoffClient("http://knowledge-studio-service:8000", transport=fake_transport)
    sources = [{"document_id": "doc-1", "chunk_index": 2, "filename": "c.pdf", "quote": "Penalización 2%"}]
    result = client.save_approved_artifact(
        user_jwt="synthetic.jwt.user",
        title="Comparativa de contratos",
        template_id="executive_brief",
        result_markdown="Resumen citado [Fuente 1].",
        sources=sources,
        evidence=sources,
    )
    assert result["status"] == "saved"
    assert result["artifact_id"] == "art_001"
    assert result["freshness_status"] == "FRESH"
    assert captured[0]["headers"]["Authorization"] == "Bearer synthetic.jwt.user"


def test_studio_handoff_rejects_ungrounded_claims_and_degrades_when_studio_offline() -> None:
    ok, errors = validate_sources_groundedness(
        [{"document_id": "doc-fake", "chunk_index": 9}],
        [{"document_id": "doc-1", "chunk_index": 0}],
    )
    assert ok is False
    assert errors

    def failing_transport(*_args):
        raise RuntimeError("503 Studio disabled")

    client = StudioHandoffClient("http://knowledge-studio-service:8000", transport=failing_transport)
    sources = [{"document_id": "doc-1", "chunk_index": 0, "filename": "a.pdf", "quote": "=SUM(A1:A2)"}]
    fallback = client.save_approved_artifact(
        user_jwt="synthetic.jwt.user",
        title="Informe",
        template_id="executive_brief",
        result_markdown="Contenido seguro",
        sources=sources,
        evidence=sources,
    )
    assert fallback["status"] == "studio_unavailable_fallback"
    assert "fallback_markdown" in fallback
    # CSV formula injection neutralized
    assert "'=SUM(A1:A2)" in fallback["fallback_csv"]

    with pytest.raises(PermissionError):
        client.save_approved_artifact(
            user_jwt="",
            title="Sin JWT",
            template_id="executive_brief",
            result_markdown="x",
            sources=sources,
            evidence=sources,
        )
