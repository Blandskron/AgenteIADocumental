from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("change", ["inactive", "password", "deleted", "missing"])
def test_revoked_identity_cannot_read_or_create(client, db_session, owner, token_headers, settings, change):
    headers = token_headers()
    assert client.get("/api/v1/exports", headers=headers).status_code == 200
    if change == "missing":
        headers = token_headers(user_id=2**63 - 1)
    else:
        query = {"inactive": "UPDATE auth_user SET is_active=FALSE WHERE id=:id",
                 "password": "UPDATE auth_user SET password='synthetic-changed' WHERE id=:id",
                 "deleted": "DELETE FROM auth_user WHERE id=:id"}[change]
        db_session.execute(text(query), {"id": int(owner)})
    for path in ["/api/v1/exports", "/api/v1/exports/missing", "/api/v1/exports/missing/status", "/api/v1/exports/missing/download"]:
        assert client.get(path, headers=headers).status_code == 401
    assert client.post("/api/v1/exports/chat-message/pdf", headers=headers, json={"answer": "synthetic"}).status_code == 401
    assert list(settings.export_storage_base_path.glob("*.pdf")) == []
    assert db_session.scalar(text("SELECT count(*) FROM document_exports WHERE owner_user_id=:id"), {"id": owner}) == 0


@pytest.fixture
def references(db_session, owner, other_id):
    ids = {name: uuid4().hex for name in ["own", "second", "other", "message", "second_message", "other_message", "inconsistent"]}
    for name, identifier in [("own", owner), ("second", owner), ("other", other_id)]:
        db_session.execute(text("INSERT INTO conversations (conversation_id,owner_user_id) VALUES (:id,:owner)"), {"id": ids[name], "owner": identifier})
    for name, conversation, identifier in [("message", "own", owner), ("second_message", "second", owner),
                                           ("other_message", "other", other_id), ("inconsistent", "own", other_id)]:
        db_session.execute(text("""INSERT INTO conversation_messages (message_id,conversation_id,owner_user_id,role,content)
                                   VALUES (:id,:conversation,:owner,'assistant','synthetic')"""),
                           {"id": ids[name], "conversation": ids[conversation], "owner": identifier})
    return ids


@pytest.mark.parametrize(("conversation", "message", "status"), [
    (None, None, 200), ("own", None, 200), (None, "message", 200), ("own", "message", 200),
    ("other", None, 404), (None, "other_message", 404), ("own", "other_message", 404),
    ("own", "second_message", 404), ("other", "message", 404), ("own", "inconsistent", 404),
    ("missing", None, 404), (None, "missing", 404), ("", None, 422), (None, "", 422),
])
def test_references_are_checked_before_rendering(client, db_session, references, token_headers, settings, owner, conversation, message, status):
    payload = {"answer": "Client snapshot, not canonical content",
               "conversation_id": references.get(conversation, conversation), "message_id": references.get(message, message)}
    before = set(settings.export_storage_base_path.glob("*.pdf"))
    response = client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(), json=payload)
    assert response.status_code == status
    if status == 200:
        saved = response.json()
        assert saved["conversation_id"] == payload["conversation_id"] and saved["message_id"] == payload["message_id"]
        assert set(settings.export_storage_base_path.glob("*.pdf")) == before
    else:
        if status == 404:
            assert response.json() == {"detail": "Export not found."}
        assert set(settings.export_storage_base_path.glob("*.pdf")) == before
        assert db_session.scalar(text("SELECT count(*) FROM document_exports WHERE owner_user_id=:id"), {"id": owner}) == 0


@pytest.mark.parametrize("claims", [{}, {"is_superuser": True, "is_superadmin": True}, {"roles": ["TENANT_ADMIN"]}])
def test_admin_claims_do_not_expand_owner_access(client, references, token_headers, other_id, claims, settings):
    other = client.post("/api/v1/exports/chat-message/pdf", headers=token_headers(user_id=int(other_id)), json={"answer": "other synthetic"}).json()
    headers = token_headers(**claims)
    assert client.get("/api/v1/exports", headers=headers).json() == []
    for suffix in ["", "/status", "/download"]:
        assert client.get("/api/v1/exports/" + other["export_id"] + suffix, headers=headers).status_code == 404
    before = set(settings.export_storage_base_path.glob("*.pdf"))
    assert client.post("/api/v1/exports/chat-message/pdf", headers=headers, json={"answer": "synthetic", "conversation_id": references["other"]}).status_code == 404
    assert set(settings.export_storage_base_path.glob("*.pdf")) == before
