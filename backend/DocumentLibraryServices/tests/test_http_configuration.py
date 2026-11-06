from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.config.settings import get_settings
from app.interfaces.api.v1.dependencies import get_library_use_case
from app.main import app


OPERATIONS = [
    ("POST", "/library/markers", {"document_ids": ["synthetic"]}),
    ("GET", "/folders", None), ("POST", "/folders", {"name": "Synthetic"}),
    ("PATCH", "/folders/synthetic", {"name": "Synthetic"}), ("DELETE", "/folders/synthetic", None),
    ("GET", "/folders/synthetic/documents", None), ("POST", "/folders/synthetic/documents/synthetic", None),
    ("DELETE", "/folders/synthetic/documents/synthetic", None),
    ("PATCH", "/library/documents/synthetic/folder", {"folder_id": None}),
    ("GET", "/library/recent", None), ("GET", "/library/favorites", None),
    ("POST", "/library/favorites/synthetic", None), ("DELETE", "/library/favorites/synthetic", None),
]


@pytest.mark.parametrize("token", [None, "synthetic-invalid-token"])
@pytest.mark.parametrize("method,path,payload", OPERATIONS)
def test_business_routes_reject_unauthenticated_requests(configured_client, monkeypatch, token, method, path, payload):
    client, _ = configured_client

    def forbidden_use_case():
        pytest.fail("Unauthenticated request reached the use case")

    monkeypatch.setitem(app.dependency_overrides, get_library_use_case, forbidden_use_case)
    response = client.request(method, f"/api/v1{path}", json=payload,
                              headers={"Authorization": f"Bearer {token}"} if token else {})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_health_and_signed_request_use_postgresql(configured_client, signing_key):
    client, _ = configured_client
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    assert client.get("/api/v1/health/db").json() == {"status": "ok"}
    token = jwt.encode({"user_id": 2147483647, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
    response = client.get("/api/v1/folders", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert set(response.json()) == {"items", "limit", "offset", "has_more"}


@pytest.mark.parametrize("origin,allowed", [
    ("http://localhost:3000", True), ("http://127.0.0.1:3000", True),
    ("https://synthetic.example", False), ("null", False),
])
def test_cors_preflight_and_actual_response(configured_client, origin, allowed):
    client, _ = configured_client
    response = client.options("/api/v1/folders", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization",
    })
    assert response.status_code == (200 if allowed else 400)
    expected = origin if allowed else None
    assert response.headers.get("access-control-allow-origin") == expected
    response = client.get("/api/v1/folders", headers={"Origin": origin})
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == expected
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize("kind", ["missing", "invalid", "non_rsa"])
def test_readiness_rejects_unavailable_or_invalid_key(configured_client, kind):
    client, settings = configured_client
    path = Path(settings.auth_jwt_public_key_path)
    if kind == "missing":
        path.unlink()
    elif kind == "invalid":
        path.write_text("Synthetic invalid key", encoding="utf-8")
    else:
        path.write_bytes(ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
    response = client.get("/api/v1/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Document library dependencies are unavailable."}
    assert client.get("/api/v1/health").status_code == 200


@pytest.mark.parametrize("table", [
    "documents", "document_assignments", "document_embeddings",
    "document_folders", "document_folder_items", "document_favorites",
])
def test_readiness_checks_each_required_table(configured_client, monkeypatch, table):
    client, _ = configured_client
    engine = create_engine(get_settings().database_url)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                # Shadow one table on this connection, leaving shared tables untouched.
                connection.execute(text(f"CREATE TEMP TABLE {table} (synthetic_wrong_column integer)"))
                with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
                    assert client.get("/api/v1/health/db").status_code == 503
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_readiness_does_not_expose_connection_details(configured_client, monkeypatch):
    class UnavailableSession:
        def execute(self, statement):
            raise SQLAlchemyError("Synthetic connection details must stay private")

    client, _ = configured_client
    monkeypatch.setitem(app.dependency_overrides, get_session, lambda: UnavailableSession())
    response = client.get("/api/v1/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Document library dependencies are unavailable."}
