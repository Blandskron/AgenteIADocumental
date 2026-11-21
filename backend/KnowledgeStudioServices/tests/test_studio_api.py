"""Smoke tests for KnowledgeStudioServices FastAPI entrypoint gated by STUDIO_ENABLED (R8-09)."""

from __future__ import annotations

import os
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_studio_api_returns_503_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_ENABLED", "false")
    client = TestClient(app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["studio_enabled"] is False

    res = client.get("/api/v1/studio/templates")
    assert res.status_code == 503


def test_studio_api_endpoints_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_ENABLED", "true")
    client = TestClient(app)

    templates = client.get("/api/v1/studio/templates")
    assert templates.status_code == 200
    assert "summary.executive" in templates.json()["templates"]

    mermaid_ok = client.post("/api/v1/studio/mermaid/validate", json={"source": "flowchart LR\nA --> B"})
    assert mermaid_ok.status_code == 200
    assert mermaid_ok.json()["status"] == "ok"

    mermaid_bad = client.post(
        "/api/v1/studio/mermaid/validate",
        json={"source": "flowchart LR\nclick A \"javascript:alert(1)\""},
    )
    assert mermaid_bad.status_code == 400

    graph = client.post(
        "/api/v1/studio/graph",
        json={"documents": [{"id": "d1", "title": "Guia", "wikilinks": ["Politica"]}]},
    )
    assert graph.status_code == 200
    assert len(graph.json()["edges"]) == 1

    review = client.post(
        "/api/v1/studio/flashcards/review",
        json={
            "card": {
                "card_id": "c1",
                "front": "Plazo?",
                "back": "97 dias",
                "citation_doc_id": "d1",
                "citation_quote": "97 dias",
            },
            "quality": 5,
        },
    )
    assert review.status_code == 200
    assert review.json()["repetitions"] == 1
    assert os.environ["STUDIO_ENABLED"] == "true"

