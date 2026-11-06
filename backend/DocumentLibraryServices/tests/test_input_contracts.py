import asyncio
import json

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.interfaces.api.body_limit import MAX_REQUEST_BYTES, RequestBodyLimit
from app.interfaces.api.v1.dependencies import get_library_use_case
from app.main import app


@pytest.fixture
def guarded(configured_client, signing_key, monkeypatch):
    client, _ = configured_client
    calls = []

    class Guard:
        def __getattr__(self, method):
            def forbidden(*args):
                calls.append(method)
                pytest.fail("Invalid input reached the use case")
            return forbidden

    monkeypatch.setitem(app.dependency_overrides, get_library_use_case, lambda: Guard())
    token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
    client.headers["Authorization"] = f"Bearer {token}"
    yield client, calls
    assert calls == []


def assert_private(response, status=422):
    assert response.status_code == status, response.text
    assert "PRIVATE_SENTINEL" not in response.text
    if status == 422:
        for error in response.json()["detail"]:
            assert set(error) == {"loc", "msg", "type"}


@pytest.mark.parametrize("name", ["", "  \t ", "x" * 201, 42, True, [], {}, None, "PRIVATE_SENTINEL\x00", "a\nb", "\ud800", "name\n", "name\x7f"])
@pytest.mark.parametrize("method,path", [("POST", "/api/v1/folders"), ("PATCH", "/api/v1/folders/valid")])
def test_invalid_names_never_reach_writes(guarded, name, method, path):
    client, _ = guarded
    response = client.request(method, path, content=json.dumps({"name": name}), headers={"Content-Type": "application/json"})
    assert_private(response)


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"metadata": None}, {"PRIVATE_SENTINEL": True}, {"name": "ok", "PRIVATE_SENTINEL": 4}])
def test_invalid_patch_has_no_writes(guarded, payload):
    assert_private(guarded[0].patch("/api/v1/folders/valid", json=payload))


@pytest.mark.parametrize("identifier", ["", " ", "x" * 129, "PRIVATE_SENTINEL\x00", 4, True, [], {}])
@pytest.mark.parametrize("field,path", [("parent_folder_id", "/api/v1/folders"), ("folder_id", "/api/v1/library/documents/valid/folder")])
def test_invalid_body_identifiers_have_no_writes(guarded, identifier, field, path):
    payload = {field: identifier}
    if field == "parent_folder_id":
        payload["name"] = "Synthetic"
    assert_private(guarded[0].request("POST" if field == "parent_folder_id" else "PATCH", path, json=payload))


@pytest.mark.parametrize("method,path", [
    ("PATCH", "/api/v1/folders/{id}"), ("DELETE", "/api/v1/folders/{id}"),
    ("GET", "/api/v1/folders/{id}/documents"),
    ("POST", "/api/v1/folders/{id}/documents/valid"), ("DELETE", "/api/v1/folders/valid/documents/{id}"),
    ("PATCH", "/api/v1/library/documents/{id}/folder"),
    ("POST", "/api/v1/library/favorites/{id}"), ("DELETE", "/api/v1/library/favorites/{id}"),
])
def test_path_identifiers_are_bounded(guarded, method, path):
    assert_private(guarded[0].request(method, path.format(id="x" * 129), json={"name": "Synthetic", "folder_id": None}))


@pytest.mark.parametrize("value", ["", "   ", "x" * 129, "PRIVATE_SENTINEL\x00"])
def test_parent_query_is_validated(guarded, value):
    assert_private(guarded[0].get("/api/v1/folders", params={"parent_folder_id": value}))


@pytest.mark.parametrize("value", [0, 101, "PRIVATE_SENTINEL", "1.5"])
def test_recent_limit_errors_are_private(guarded, value):
    assert_private(guarded[0].get("/api/v1/library/recent", params={"limit": value}))


def nested(depth):
    value = "PRIVATE_SENTINEL"
    for _ in range(depth):
        value = [value]
    return {"key": value}


@pytest.mark.parametrize("metadata", [[], "PRIVATE_SENTINEL", None, {"key": "x" * 16_377},
    {"PRIVATE_SENTINEL\x00": "value"}, {"key": "PRIVATE_SENTINEL\x00"}, {"key": "\ud800"},
    {"key": float("nan")}, {"key": float("inf")}, nested(16),
])
@pytest.mark.parametrize("method,path", [("POST", "/api/v1/folders"), ("PATCH", "/api/v1/folders/valid")])
def test_invalid_metadata_has_no_writes(guarded, metadata, method, path):
    assert_private(guarded[0].request(method, path, content=json.dumps({"name": "ok", "metadata": metadata}),
                                    headers={"Content-Type": "application/json"}))


@pytest.mark.parametrize("payload", [{}, {"folder_id": None, "PRIVATE_SENTINEL": 4}])
def test_move_requires_explicit_destination_and_rejects_unknown_fields(guarded, payload):
    assert_private(guarded[0].patch("/api/v1/library/documents/valid/folder", json=payload))


def test_malformed_json_is_private(guarded):
    assert_private(guarded[0].post("/api/v1/folders", content='{"PRIVATE_SENTINEL":', headers={"Content-Type": "application/json"}))


@pytest.mark.parametrize("raw,status", [
    (b"\xff", 400), (b"[" * 64 + b"0" + b"]" * 64, 422), (b'{"name":' + b"1" * 5000 + b"}", 400),
], ids=["invalid-utf8", "nested-non-object", "oversized-integer"])
def test_unusable_body_returns_private_error(guarded, raw, status):
    assert_private(guarded[0].post("/api/v1/folders", content=raw, headers={"Content-Type": "application/json"}), status)


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE", "GET"])
def test_oversized_http_body_is_rejected_before_use_case(guarded, method):
    response = guarded[0].request(method, "/api/v1/folders/valid" if method != "POST" else "/api/v1/folders",
                                  content=b"x" * (MAX_REQUEST_BYTES + 1), headers={"Origin": "http://localhost:3000"})
    assert_private(response, 413)
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.parametrize("size,expected", [(MAX_REQUEST_BYTES, 204), (MAX_REQUEST_BYTES + 1, 413)])
@pytest.mark.parametrize("declared", [None, b"1"])
def test_stream_limit_uses_actual_bytes(size, expected, declared):
    async def run():
        messages = [{"type": "http.request", "body": b"x" * 32768, "more_body": True},
                    {"type": "http.request", "body": b"x" * (size - 32768), "more_body": False}]
        sent, received = [], []

        async def receive():
            return messages.pop(0)

        async def send(message):
            sent.append(message)

        async def downstream(scope, receive, send):
            received.append((await receive())["body"])
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        scope = {"type": "http", "method": "POST", "headers": [] if declared is None else [(b"content-length", declared)]}
        await RequestBodyLimit(downstream)(scope, receive, send)
        assert sent[0]["status"] == expected
        assert received == ([b"x" * size] if expected == 204 else [])
    asyncio.run(run())


def test_valid_boundaries_round_trip_and_error_does_not_poison_session(migrated_database, configured_client, signing_key, monkeypatch):
    client, _ = configured_client
    token = jwt.encode({"user_id": 42, "exp": 4102444800, "token_type": "access"}, signing_key, algorithm="RS256")
    client.headers["Authorization"] = f"Bearer {token}"
    with Session(migrated_database) as session:
        monkeypatch.setitem(app.dependency_overrides, get_session, lambda: session)
        metadata = {"key": "ñ" * 8187}  # 10 bytes of JSON punctuation + 16374 bytes = 16384.
        response = client.post("/api/v1/folders", json={"name": "  " + "ñ" * 200 + "  ", "metadata": metadata})
        assert response.status_code == 201, response.text
        folder_id = response.json()["folder_id"]
        assert response.json()["name"] == "ñ" * 200
        assert response.json()["metadata"] == metadata
        assert client.patch(f"/api/v1/folders/{folder_id}", json={"metadata": nested(15)}).status_code == 200
        assert client.patch(f"/api/v1/folders/{folder_id}", json={"name": " \t "}).status_code == 422
        assert client.get("/api/v1/folders").json()[0]["name"] == "ñ" * 200
        assert client.patch(f"/api/v1/folders/{folder_id}", json={"metadata": {}}).status_code == 200
        assert client.post("/api/v1/folders", json={"name": "ñ" * 200}).status_code == 409
        assert client.post("/api/v1/folders", json={"name": "child", "parent_folder_id": "missing"}).status_code == 404
        assert client.get("/api/v1/folders", params={"parent_folder_id": "x" * 128}).status_code == 404
        session.commit()
        with migrated_database.begin() as connection:
            connection.exec_driver_sql("""CREATE FUNCTION synthetic_failure() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'PRIVATE_SENTINEL SQL internals'; END $$;
                CREATE TRIGGER synthetic_failure BEFORE INSERT ON document_folders FOR EACH ROW EXECUTE FUNCTION synthetic_failure();""")
        failed = client.post("/api/v1/folders", json={"name": "failure"})
        assert_private(failed, 500)
        assert failed.json() == {"detail": "Database operation failed."}
        assert session.scalar(text("SELECT count(*) FROM document_folders")) == 1
        session.commit()
        with migrated_database.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER synthetic_failure ON document_folders")
        assert client.post("/api/v1/folders", json={"name": "Recovery"}).status_code == 201
        raw = b'{"name":"Exact boundary"}'
        raw += b" " * (MAX_REQUEST_BYTES - len(raw))
        assert client.post("/api/v1/folders", content=raw, headers={"Content-Type": "application/json"}).status_code == 201
        assert client.post("/api/v1/folders", content=raw + b" ", headers={"Content-Type": "application/json"}).status_code == 413
        assert session.scalar(text("SELECT count(*) FROM document_folders")) == 3


def test_openapi_documents_constraints(configured_client):
    schema = configured_client[0].get("/openapi.json").json()
    create = schema["components"]["schemas"]["FolderCreateRequest"]
    assert create["additionalProperties"] is False
    assert create["properties"]["name"]["maxLength"] == 200
    move = schema["components"]["schemas"]["DocumentMoveRequest"]
    assert move["required"] == ["folder_id"]
    assert {"400", "404", "409", "413", "422", "500"} <= schema["paths"]["/api/v1/folders"]["post"]["responses"].keys()
