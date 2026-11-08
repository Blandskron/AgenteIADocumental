from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.database.repositories.export_repository_pg import ExportRepositoryPg

pytestmark = pytest.mark.postgres


def test_atomic_blob_checksum_idempotency_and_delete(client, token_headers, db_session, settings, other_id):
    headers = {**token_headers(), "Idempotency-Key": str(uuid4())}
    payload = {"answer": "Documento íntegro", "metadata": {"b": 2, "a": 1}}
    first = client.post("/api/v1/exports/chat-message/pdf", headers=headers, json=payload)
    assert first.status_code == 200
    saved = first.json()
    second = client.post("/api/v1/exports/chat-message/pdf", headers=headers,
                         json={**payload, "metadata": {"a": 1, "b": 2}})
    assert second.json()["export_id"] == saved["export_id"]
    assert client.post("/api/v1/exports/chat-message/pdf", headers=headers, json={"answer": "different"}).status_code == 409
    download = client.get(saved["download_url"], headers=token_headers())
    assert sha256(download.content).hexdigest() == saved["sha256"]
    assert download.headers["cache-control"] == "private, no-store" and download.headers["x-content-type-options"] == "nosniff"
    assert not list(settings.export_storage_base_path.glob("*.pdf"))
    assert client.delete("/api/v1/exports/" + saved["export_id"], headers=token_headers(user_id=2**63-1)).status_code == 401
    assert client.delete("/api/v1/exports/" + saved["export_id"], headers=token_headers(user_id=int(other_id), is_superadmin=True)).status_code == 404
    assert client.delete("/api/v1/exports/" + saved["export_id"], headers=token_headers()).json() == {"deleted": True}
    assert client.get(saved["download_url"], headers=token_headers()).status_code == 404
    assert db_session.scalar(text("SELECT count(*) FROM document_exports WHERE export_id=:id"), {"id": saved["export_id"]}) == 0


def test_persistence_failure_creates_no_file_or_row(client, token_headers, db_session, settings, monkeypatch, owner):
    def fail(*args, **kwargs): raise SQLAlchemyError("private failure")
    monkeypatch.setattr(ExportRepositoryPg, "create_export", fail)
    response = client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "synthetic"})
    assert response.status_code == 503 and "private" not in response.text
    assert not settings.export_storage_base_path.exists()
    assert db_session.scalar(text("SELECT count(*) FROM document_exports WHERE owner_user_id=:id"), {"id": owner}) == 0


def test_legacy_path_never_read_and_expiry_is_coherent(client, token_headers, db_session, owner, tmp_path):
    path = tmp_path / "private.txt"
    path.write_text("Never served")
    identifier = uuid4().hex
    db_session.execute(text("""INSERT INTO document_exports
        (export_id,owner_user_id,source_type,title,filename,storage_path) VALUES (:id,:owner,'chat_message','Legacy','legacy.pdf',:path)
    """), {"id": identifier, "owner": owner, "path": str(path)})
    assert client.get(f"/api/v1/exports/{identifier}/status", headers=token_headers()).json()["status"] == "MIGRATION_REQUIRED"
    assert client.get(f"/api/v1/exports/{identifier}/download", headers=token_headers()).status_code == 409
    assert path.read_text() == "Never served"
    saved = client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "synthetic"}).json()
    db_session.execute(text("UPDATE document_exports SET expires_at=:expiry WHERE export_id=:id"),
                       {"id": saved["export_id"], "expiry": datetime.now(UTC) - timedelta(seconds=1)})
    db_session.expire_all()
    assert client.get(f"/api/v1/exports/{saved['export_id']}/status", headers=token_headers()).json()["status"] == "EXPIRED"
    assert client.get(saved["download_url"], headers=token_headers()).status_code == 410


def test_quota_rolls_back_generated_bytes(client, token_headers, monkeypatch, db_session, owner):
    monkeypatch.setattr("app.config.export_limits.OWNER_COUNT", 1)
    assert client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "one"}).status_code == 200
    assert client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "two"}).status_code == 409
    assert db_session.scalar(text("SELECT count(*) FROM document_exports WHERE owner_user_id=:id"), {"id": owner}) == 1


@pytest.mark.parametrize("quota", ["OWNER_BYTES", "GLOBAL_BYTES"])
def test_byte_quota_cannot_be_bypassed(client, token_headers, monkeypatch, quota, db_session, owner):
    monkeypatch.setattr("app.config.export_limits." + quota, 1)
    assert client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "bounded"}).status_code == 409
    assert db_session.scalar(text("SELECT count(*) FROM document_exports WHERE owner_user_id=:id"), {"id": owner}) == 0


def test_database_rejects_corruption_before_commit(client, token_headers, db_session):
    from sqlalchemy.exc import IntegrityError
    saved = client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json={"answer": "integrity"}).json()
    transaction = db_session.begin_nested()
    with pytest.raises(IntegrityError):
        db_session.execute(text("UPDATE document_exports SET pdf_data=:bad WHERE export_id=:id"), {"id": saved["export_id"], "bad": b"corrupt"})
    transaction.rollback()
    assert client.get(saved["download_url"], headers=token_headers()).status_code == 200


def test_parallel_same_operation_and_restart_do_not_duplicate(committed_engine, settings, token_headers, owner):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import create_app
    configured = settings.model_copy(update={"db_timeout_seconds": 15})
    barrier, key = Barrier(2), str(uuid4())
    headers = {**token_headers(), "Idempotency-Key": key}
    def submit():
        with TestClient(create_app(configured)) as client:
            barrier.wait(5)
            response = client.post("/api/v1/exports/chat-message/pdf", headers=headers, json={"answer": "exact operation"})
            assert response.status_code == 200
            return response.json()["export_id"]
    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(lambda _: submit(), range(2)))
    assert ids[0] == ids[1]
    with TestClient(create_app(configured)) as restarted:
        assert restarted.post("/api/v1/exports/chat-message/pdf", headers=headers, json={"answer": "exact operation"}).json()["export_id"] == ids[0]
        assert restarted.get(f"/api/v1/exports/{ids[0]}/download", headers=token_headers()).content.startswith(b"%PDF-")
    with committed_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM document_exports WHERE owner_user_id=:owner"), {"owner": owner}) == 1
