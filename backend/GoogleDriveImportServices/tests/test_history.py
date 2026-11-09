from contextlib import contextmanager

import base64
import json

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres
URL = "/api/v1/google-drive/imports"


@pytest.fixture
def history(engine, identities):
    with engine.begin() as c:
        for owner in ("owner", "other"):
            for index in range(7):
                c.execute(
                    text("""INSERT INTO google_drive_imports
                    (import_id,owner_user_id,status,created_at,metadata,error_message)
                    VALUES(:id,:owner,'COMPLETED','2026-01-01T00:00:00Z',
                    '{"access_token":"synthetic-private","source":"legacy","folder_id":"folder"}',
                    'synthetic-private')"""),
                    {
                        "id": f"{identities[owner]}-{index:02}",
                        "owner": str(identities[owner]),
                    },
                )
        parent = f"{identities['owner']}-06"
        for index in range(7):
            c.execute(
                text("""INSERT INTO google_drive_import_files
                (import_file_id,import_id,google_file_id,filename,mime_type,status,created_at,metadata,error_message)
                VALUES(:id,:parent,'synthetic-file','synthetic.txt','text/plain','COMPLETED',
                '2026-01-01T00:00:00Z','{"access_token":"synthetic-private",
                "document_status":"PROCESSED","folder_association":{"status":"FAILED","error":"synthetic-private"}}',
                'synthetic-private')"""),
                {"id": f"file-{index:02}", "parent": parent},
            )
    return parent


def test_stable_owner_pages_and_new_insert(client, token, engine, identities, history):
    headers = token()
    first = client.get(URL, params={"limit": 3}, headers=headers)
    assert first.status_code == 200
    assert "no-store" in first.headers["cache-control"]
    page = first.json()
    ids = [row["import_id"] for row in page["items"]]
    assert ids == [f"{identities['owner']}-{i:02}" for i in (6, 5, 4)]
    assert "synthetic-private" not in first.text
    assert page["items"][0]["metadata"] == {
        "source": "google_drive",
        "folder_id": "folder",
    }
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO google_drive_imports(owner_user_id,status) VALUES(:u,'COMPLETED')"
            ),
            {"u": str(identities["owner"])},
        )
    while page["next_cursor"]:
        response = client.get(
            URL, params={"limit": 3, "before": page["next_cursor"]}, headers=headers
        )
        assert response.status_code == 200
        page = response.json()
        ids += [row["import_id"] for row in page["items"]]
    assert ids == [f"{identities['owner']}-{i:02}" for i in range(6, -1, -1)]


def test_files_paging_whitelist_and_parent_scope(client, token, identities, history):
    url = f"{URL}/{history}/files"
    page = client.get(url, params={"limit": 3}, headers=token()).json()
    rows = page["items"]
    cursor = page["next_cursor"]
    assert rows[0]["metadata"] == {
        "document_status": "PROCESSED",
        "folder_association": {"status": "FAILED"},
    }
    assert "synthetic-private" not in json.dumps(rows)
    while page["next_cursor"]:
        page = client.get(
            url, params={"limit": 3, "after": page["next_cursor"]}, headers=token()
        ).json()
        rows += page["items"]
    assert [row["import_file_id"] for row in rows] == [f"file-{i:02}" for i in range(7)]
    assert (
        client.get(URL, params={"before": cursor}, headers=token()).status_code == 400
    )
    assert (
        client.get(
            f"{URL}/{identities['owner']}-05/files",
            params={"after": cursor},
            headers=token(),
        ).status_code
        == 400
    )
    assert (
        client.get(url, headers=token(user_id=identities["other"])).status_code == 404
    )
    with base64_error_cursor(cursor) as forged:
        assert (
            client.get(url, params={"after": forged}, headers=token()).status_code
            == 400
        )


@contextmanager
def base64_error_cursor(cursor):
    value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    value["owner"] = "another-owner"
    yield base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"before": ""}, {"before": "a" * 1025}]
)
def test_page_bounds(client, token, params):
    assert client.get(URL, params=params, headers=token()).status_code == 422


@pytest.mark.parametrize("cursor", ["bad", "e30", "a.b", "W10", "_w"])
def test_invalid_cursors_fail_closed(client, token, cursor):
    assert (
        client.get(URL, params={"before": cursor}, headers=token()).status_code == 400
    )


def test_purged_files_hidden_and_revoked_permission(
    client, token, engine, identities, history
):
    with engine.begin() as c:
        c.execute(
            text("UPDATE google_drive_imports SET status='PURGED' WHERE import_id=:i"),
            {"i": history},
        )
    assert client.get(f"{URL}/{history}/files", headers=token()).json() == {
        "items": [],
        "next_cursor": None,
    }
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM tenant_group_permissions WHERE group_id=:g"),
            {"g": identities["group"]},
        )
    assert client.get(f"{URL}/{history}/files", headers=token()).status_code == 403
