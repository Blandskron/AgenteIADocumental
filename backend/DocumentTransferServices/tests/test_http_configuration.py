from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.infrastructure.database.models import DocumentAssignmentModel, DocumentModel, TransferEventModel
from app.main import app


@pytest.mark.parametrize("token", [None, "synthetic-invalid-token"])
@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/transfers", None),
    ("POST", "/transfers", {"filename": "synthetic.txt", "direction": "UPLOAD"}),
    ("PATCH", "/transfers/synthetic", {"progress": 10}),
    ("DELETE", "/transfers/history", None),
])
def test_business_routes_require_authentication(configured_client, token, method, path, payload):
    client, _ = configured_client
    response = client.request(method, f"/api/v1{path}", json=payload,
                              headers={"Authorization": f"Bearer {token}"} if token else {})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("origin,allowed", [
    ("http://localhost:3000", True), ("http://127.0.0.1:3000", True),
    ("https://synthetic.example", False), ("null", False),
])
def test_preflight_and_actual_cors(configured_client, origin, allowed):
    client, _ = configured_client
    response = client.options("/api/v1/transfers", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization",
    })
    assert response.status_code == (200 if allowed else 400)
    assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)
    response = client.get("/api/v1/transfers", headers={"Origin": origin})
    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)
    assert "access-control-allow-credentials" not in response.headers


@pytest.mark.parametrize("kind", ["missing", "invalid", "non_rsa"])
def test_readiness_rejects_invalid_key_and_recovers(configured_client, kind):
    client, settings = configured_client
    path = Path(settings.auth_jwt_public_key_path)
    original = path.read_bytes()
    if kind == "missing":
        path.unlink()
    elif kind == "invalid":
        path.write_text("Synthetic malformed key", encoding="utf-8")
    else:
        path.write_bytes(ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
    response = client.get("/api/v1/health/db")
    assert response.status_code == 503
    assert response.json() == {"detail": "Document transfer dependencies are unavailable."}
    assert client.get("/api/v1/health").json() == {"status": "ok"}
    path.write_bytes(original)
    assert client.get("/api/v1/health/db").status_code == 200


@pytest.mark.parametrize("missing_column", list(TransferEventModel.__table__.columns.keys()))
def test_readiness_checks_every_column_without_reading_history(configured_client, engine, missing_column):
    client, _ = configured_client
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            columns = ", ".join(f'"{column}"' for column in TransferEventModel.__table__.columns.keys()
                                if column != missing_column)
            # Only this connection sees the temporary shadow; shared schema is untouched.
            connection.execute(text(f"CREATE TEMP TABLE transfer_events AS SELECT {columns} FROM public.transfer_events WHERE false"))
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                app.dependency_overrides[get_session] = lambda: session
                response = client.get("/api/v1/health/db")
                assert response.status_code == 503
                assert response.json() == {"detail": "Document transfer dependencies are unavailable."}
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
    assert client.get("/api/v1/health/db").status_code == 200


def test_database_outage_returns_private_503_and_recovers(configured_client):
    client, _ = configured_client
    unavailable = create_engine("postgresql+psycopg://synthetic:synthetic@127.0.0.1:1/synthetic", connect_args={"connect_timeout": 1})
    try:
        with Session(unavailable) as session:
            app.dependency_overrides[get_session] = lambda: session
            response = client.get("/api/v1/health/db")
            assert response.status_code == 503
            assert response.json() == {"detail": "Document transfer dependencies are unavailable."}
            assert client.get("/api/v1/health").status_code == 200
    finally:
        app.dependency_overrides.pop(get_session, None)
        unavailable.dispose()
    assert client.get("/api/v1/health/db").status_code == 200


@pytest.mark.parametrize("model", [DocumentModel, DocumentAssignmentModel])
def test_readiness_requires_reference_permission_schema(configured_client, engine, model):
    client, _ = configured_client
    table = model.__tablename__
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f"CREATE TEMP TABLE {table} (synthetic_wrong_column integer)"))
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                app.dependency_overrides[get_session] = lambda: session
                assert client.get("/api/v1/health/db").status_code == 503
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
    assert client.get("/api/v1/health/db").status_code == 200


def test_signed_create_list_update_and_cleanup_are_rolled_back(configured_client, signing_key, engine):
    client, _ = configured_client
    owner = int(uuid4().hex[:12], 16)
    token = jwt.encode({"user_id": owner, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
    headers = {"Authorization": f"Bearer {token}"}
    transfer_id = None
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                app.dependency_overrides[get_session] = lambda: session
                assert client.get("/api/v1/health/db").status_code == 200
                response = client.post("/api/v1/transfers", headers=headers,
                                       json={"filename": "synthetic.txt", "direction": "UPLOAD"})
                assert response.status_code == 200
                transfer_id = response.json()["transfer_id"]
                assert response.json()["owner_user_id"] == str(owner)
                assert [row["transfer_id"] for row in client.get("/api/v1/transfers", headers=headers).json()["items"]] == [transfer_id]
                response = client.patch(f"/api/v1/transfers/{transfer_id}", headers=headers,
                                        json={"status": "COMPLETED", "progress": 100})
                assert response.status_code == 200
                assert response.json()["status"] == "COMPLETED"
                assert response.json()["progress"] == 100
                assert client.delete("/api/v1/transfers/history", headers=headers).json() == {"count": 1}
                assert client.get("/api/v1/transfers", headers=headers).json()["items"] == []
                # Leave a committed savepoint row to prove the outer rollback removes it.
                remaining = client.post("/api/v1/transfers", headers=headers,
                                        json={"filename": "synthetic-rollback.txt", "direction": "DOWNLOAD"})
                assert remaining.status_code == 200
                assert connection.scalar(select(TransferEventModel.transfer_id).where(
                    TransferEventModel.transfer_id == remaining.json()["transfer_id"])) is not None
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
    with engine.connect() as connection:
        assert connection.scalar(select(TransferEventModel.transfer_id).where(TransferEventModel.transfer_id == transfer_id)) is None
        assert connection.scalar(select(TransferEventModel.transfer_id).where(TransferEventModel.owner_user_id == str(owner))) is None
