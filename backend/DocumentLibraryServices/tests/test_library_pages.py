import jwt
import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.main import app


@pytest.fixture
def pages(migrated_database, configured_client, signing_key, monkeypatch):
    engine = migrated_database
    client, _ = configured_client
    token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
    client.headers["Authorization"] = f"Bearer {token}"
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO tenants(tenant_id,name) VALUES ('pages','Synthetic pages')"))
        for i in range(7):
            connection.execute(text("INSERT INTO document_folders(folder_id,name,owner_user_id) VALUES (:id,:id,'42')"), {"id": f"f{i}"})
        connection.execute(text("INSERT INTO document_folders(folder_id,name,owner_user_id,parent_folder_id) VALUES ('child','Child','42','f0'),('foreign','Foreign','43',NULL)"))
        for i in range(1, 10):
            identifier = f"d{i:03}"
            connection.execute(text("""INSERT INTO documents(document_id,filename,storage_path,mime_type,owner_user_id,status,updated_at)
                VALUES (:id,'synthetic.txt','synthetic-pages.txt','text/plain',:owner,'PROCESSED','2026-01-01T00:00:00Z')"""),
                               {"id": identifier, "owner": "42" if i < 9 else "43"})
            connection.execute(text("INSERT INTO document_favorites(document_id,owner_user_id,created_at) VALUES (:id,'42','2026-01-01T00:00:00Z')"), {"id": identifier})
            connection.execute(text("INSERT INTO document_folder_items(folder_id,document_id,owner_user_id,added_at) VALUES ('f0',:id,'42','2026-01-01T00:00:00Z')"), {"id": identifier})
            connection.execute(text("""INSERT INTO document_embeddings(document_id,chunk_index,chunk_content,embedding)
                VALUES (:id,0,'Synthetic',array_fill(1.0::real,ARRAY[384])::vector)"""), {"id": identifier})
    with Session(engine) as session:
        monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
        yield client, session, engine


@pytest.mark.parametrize("path", ["/library/recent", "/library/favorites", "/folders/f0/documents"])
def test_document_pages_have_stable_ties_and_visible_counts(pages, path):
    client, _, _ = pages
    seen = []
    for offset, expected_more in [(0, True), (3, True), (6, False), (9, False)]:
        response = client.get(f"/api/v1{path}", params={"limit": 3, "offset": offset})
        assert response.status_code == 200
        page = response.json()
        assert set(page) == {"items", "limit", "offset", "has_more"}
        assert (page["limit"], page["offset"], page["has_more"]) == (3, offset, expected_more)
        seen.extend(item["document_id"] for item in page["items"])
        assert all(item["chunk_count"] == 1 and item["is_favorite"] is True for item in page["items"])
    assert seen == [f"d{i:03}" for i in range(8, 0, -1)]
    folders = client.get("/api/v1/folders").json()["items"]
    assert folders[0]["document_count"] == 8
    assert all(folder["document_count"] == 0 for folder in folders[1:])


def test_root_and_child_pages_preserve_parent_privacy(pages):
    client, _, _ = pages
    identifiers = []
    for offset in (0, 3, 6):
        page = client.get("/api/v1/folders", params={"limit": 3, "offset": offset}).json()
        identifiers += [item["folder_id"] for item in page["items"]]
        assert page["has_more"] == (offset < 6)
    assert identifiers == [f"f{i}" for i in range(7)]
    child = client.get("/api/v1/folders", params={"parent_folder_id": "f0", "limit": 1}).json()
    assert [row["folder_id"] for row in child["items"]] == ["child"] and not child["has_more"]
    assert client.get("/api/v1/folders", params={"parent_folder_id": "foreign", "offset": 100}).status_code == 404
    assert client.get("/api/v1/folders/foreign/documents", params={"offset": 100}).status_code == 404


@pytest.mark.parametrize("path", ["/folders", "/folders/f0/documents", "/library/recent", "/library/favorites"])
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 1_000_001}, {"offset": "PRIVATE_SENTINEL"}])
def test_page_boundaries_are_validated(pages, path, params):
    response = pages[0].get(f"/api/v1{path}", params=params)
    assert response.status_code == 422
    assert "PRIVATE_SENTINEL" not in response.text


@pytest.mark.parametrize("path,queries", [("/folders", 1), ("/library/recent", 3), ("/library/favorites", 3), ("/folders/f0/documents", 4)])
def test_list_query_count_is_independent_of_page_size(pages, path, queries):
    client, session, engine = pages
    counts = []
    for size in (1, 7):
        statements = []

        def record(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        session.expire_all()
        event.listen(engine, "before_cursor_execute", record)
        try:
            assert client.get(f"/api/v1{path}", params={"limit": size}).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", record)
        counts.append(len(statements))
    assert counts == [queries, queries]


def test_marker_batch_filters_access_and_revocation_without_granting_it(pages):
    client, session, _ = pages
    ids = ["d001", "d009", "missing", "d001"]
    response = client.post("/api/v1/library/markers", json={"document_ids": ids})
    assert response.json() == [{"document_id": "d001", "is_favorite": True}]
    session.execute(text("INSERT INTO document_assignments(document_id,tenant_id,assigned_to_user_id,assigned_by_user_id,status) VALUES ('d009','pages','42','43','PENDING')"))
    assert len(client.post("/api/v1/library/markers", json={"document_ids": ids}).json()) == 2
    assert client.get("/api/v1/library/recent", params={"limit": 1}).json()["items"][0]["document_id"] == "d009"
    session.execute(text("UPDATE document_assignments SET status='CANCELLED' WHERE document_id='d009'"))
    assert client.post("/api/v1/library/markers", json={"document_ids": ids}).json() == response.json()
    assert client.get("/api/v1/library/recent", params={"limit": 1}).json()["items"][0]["document_id"] == "d008"
    session.execute(text("DELETE FROM document_favorites WHERE document_id='d001' AND owner_user_id='42'"))
    assert client.post("/api/v1/library/markers", json={"document_ids": ids}).json() == [{"document_id": "d001", "is_favorite": False}]


@pytest.mark.parametrize("payload", [{"document_ids": []}, {"document_ids": ["x"] * 101}, {"document_ids": ["x" * 129]}, {"document_ids": [True]}, {"document_ids": ["x"], "PRIVATE_SENTINEL": 2}])
def test_marker_batches_are_bounded(pages, payload):
    response = pages[0].post("/api/v1/library/markers", json=payload)
    assert response.status_code == 422 and "PRIVATE_SENTINEL" not in response.text
