import base64
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def seed(session, owner):
    for index in range(5):
        session.execute(text("""INSERT INTO document_exports(export_id,owner_user_id,source_type,title,filename,storage_path,created_at)
            VALUES (:id,:owner,'chat_message','Synthetic','legacy.pdf','',:at)"""),
                        {"id": f"page-{index}", "owner": owner, "at": datetime(2026, 1, 1, tzinfo=UTC)})


def test_cursor_order_ties_deletion_insert_and_owner_scope(client, db_session, token_headers, owner, other_id):
    seed(db_session, owner)
    first = client.get("/api/v1/exports?limit=2", headers=token_headers())
    assert first.status_code == 200 and first.headers["cache-control"] == "private, no-store"
    first = first.json()
    assert [row["export_id"] for row in first["items"]] == ["page-4", "page-3"]
    cursor = first["next_cursor"]
    assert client.get("/api/v1/exports", params={"before": cursor}, headers=token_headers(user_id=int(other_id))).status_code == 400
    assert client.get("/api/v1/exports", params={"before": cursor, "source_type": "unmatched"}, headers=token_headers()).status_code == 400
    db_session.execute(text("DELETE FROM document_exports WHERE export_id='page-3'"))
    db_session.execute(text("""INSERT INTO document_exports(owner_user_id,source_type,title,filename,storage_path)
                              VALUES (:owner,'chat_message','Newer','new.pdf','')"""), {"owner": owner})
    second = client.get("/api/v1/exports", params={"limit": 2, "before": cursor}, headers=token_headers()).json()
    assert [row["export_id"] for row in second["items"]] == ["page-2", "page-1"]
    last = client.get("/api/v1/exports", params={"limit": 2, "before": second["next_cursor"]}, headers=token_headers()).json()
    assert [row["export_id"] for row in last["items"]] == ["page-0"] and last["next_cursor"] is None


@pytest.mark.parametrize("query", [{"limit": 0}, {"limit": 51}, {"before": "x" * 513}])
def test_pagination_limits(client, token_headers, query):
    assert client.get("/api/v1/exports", params=query, headers=token_headers()).status_code == 422


@pytest.mark.parametrize("cursor", ["bad!", "null", "[]", "{}", '{"v":true}', '{"at":"2026-01-01","id":"x"}'])
def test_invalid_cursor_is_sanitized(client, token_headers, cursor):
    value = base64.urlsafe_b64encode(cursor.encode()).decode() if cursor != "bad!" else cursor
    response = client.get("/api/v1/exports", params={"before": value}, headers=token_headers())
    assert response.status_code == 400 and response.json() == {"detail": "Invalid export request."}
