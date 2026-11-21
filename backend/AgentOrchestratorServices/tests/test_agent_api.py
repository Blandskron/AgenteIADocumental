from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_agent_api_health_and_401_without_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTS_ENABLED", "false")
    client = TestClient(app)

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["agents_enabled"] is False
    assert health.json()["code_mode_enabled"] is False

    unauth = client.get("/api/v1/agents/tools")
    assert unauth.status_code == 401

