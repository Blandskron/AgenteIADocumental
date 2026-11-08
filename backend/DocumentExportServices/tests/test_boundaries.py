import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.interfaces.api.v1.dependencies import get_export_use_case
from app.main import create_app
from app.shared.errors import ExportGenerationError, NotFoundError, ValidationError


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000", "https://external.invalid"])
def test_cors_is_limited_to_configured_origins(settings, origin):
    client = TestClient(create_app(settings))
    response = client.options("/api/v1/exports", headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
    if origin in settings.cors_origins:
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    else:
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(("error", "status"), [
    (NotFoundError("synthetic-private-detail"), 404), (ValidationError("synthetic-private-detail"), 400),
    (ExportGenerationError("synthetic-private-detail"), 500), (SQLAlchemyError("synthetic-private-detail"), 503),
    (IntegrityError("synthetic-private-query", {"secret": "synthetic-private-detail"}, Exception("private")), 409),
])
def test_internal_errors_are_not_reflected(settings, token_headers, error, status):
    app = create_app(settings)
    def failed():
        raise error
    app.dependency_overrides[get_export_use_case] = failed
    response = TestClient(app).get("/api/v1/exports", headers=token_headers())
    assert response.status_code == status
    assert "private" not in response.text


def test_validation_does_not_reflect_input(settings, token_headers):
    app = create_app(settings)
    app.dependency_overrides[get_export_use_case] = lambda: object()
    response = TestClient(app).post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": {"private-key": "private-value"}})
    assert response.status_code == 422
    assert "private" not in response.text
    assert "input" not in response.text


@pytest.mark.parametrize("claims", [{"token_type": "refresh"}, {"exp": 1}])
def test_invalid_access_is_rejected_without_database(settings, token_headers, claims):
    assert TestClient(create_app(settings)).get("/api/v1/exports", headers=token_headers(**claims)).status_code == 401


def test_missing_auth_rejected(settings):
    assert TestClient(create_app(settings)).get("/api/v1/exports").status_code == 401


def test_public_key_is_not_cached(settings, token_headers):
    app = create_app(settings)
    class Exports:
        def list_exports(self, source_type): return []
    app.dependency_overrides[get_export_use_case] = lambda: Exports()
    client = TestClient(app)
    assert client.get("/api/v1/exports", headers=token_headers()).status_code == 200
    settings.auth_jwt_public_key_path.write_bytes(b"synthetic-invalid-key")
    response = client.get("/api/v1/exports", headers=token_headers())
    assert response.status_code == 401 and "invalid-key" not in response.text
