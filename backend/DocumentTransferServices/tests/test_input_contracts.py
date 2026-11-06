import asyncio
import json
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.database import get_session
from app.interfaces.api.body_limit import MAX_REQUEST_BYTES
from app.main import app


@pytest.fixture
def records(configured_client, signing_key, engine):
    client, _ = configured_client
    owner = int(uuid4().hex[:12], 16)
    document = uuid4().hex
    headers = {"Authorization": "Bearer " + jwt.encode({"user_id": owner, "exp": 4102444800, "token_type": "access"},
                                                       signing_key, algorithm="RS256")}
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                session.execute(text("""
                    INSERT INTO documents (document_id, owner_user_id, filename, storage_path, mime_type)
                    VALUES (:id, :owner, 'synthetic.txt', 'synthetic.txt', 'text/plain')
                """), {"id": document, "owner": str(owner)})
                session.commit()
                app.dependency_overrides[get_session] = lambda: session
                yield client, session, headers, owner, document
        finally:
            app.dependency_overrides.pop(get_session, None)
            transaction.rollback()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)}) == 0
        assert connection.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": document}) == 0


def create(client, headers, **changes):
    return client.post("/api/v1/transfers", headers=headers,
                       json={"filename": "synthetic.txt", "direction": "UPLOAD", **changes})


def event_count(session, owner):
    return session.scalar(text("SELECT count(*) FROM transfer_events WHERE owner_user_id=:owner"), {"owner": str(owner)})


def assert_private(response, status):
    assert response.status_code == status
    assert "sensitive-synthetic" not in response.text
    assert "input" not in response.text
    assert "ctx" not in response.text


def test_metadata_round_trip_uses_real_column_and_patch_nulls_are_explicit(records):
    client, session, headers, owner, document = records
    metadata = {"conversation_id": "synthetic-session", "error": "sensitive-synthetic", "nested": [None, 1, True, "日本語"]}
    response = create(client, headers, document_id=document, size_bytes=0, metadata=metadata)
    assert response.status_code == 200
    identifier = response.json()["transfer_id"]
    assert response.json()["metadata"] == metadata
    assert session.scalar(text("SELECT metadata FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}) == metadata
    assert client.get("/api/v1/transfers", headers=headers).json()[0]["metadata"] == metadata
    response = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"progress": 50})
    assert response.json()["metadata"] == metadata
    assert response.json()["document_id"] == document
    assert response.json()["size_bytes"] == 0
    replacement = {"conversation_id": None, "error": "synthetic-second"}
    response = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"metadata": replacement})
    assert response.status_code == 200 and response.json()["metadata"] == replacement
    assert session.scalar(text("SELECT metadata FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}) == replacement
    response = client.patch(f"/api/v1/transfers/{identifier}", headers=headers,
                            json={"metadata": {}, "document_id": None, "size_bytes": None})
    assert response.status_code == 200
    assert response.json()["metadata"] == {} and response.json()["document_id"] is None and response.json()["size_bytes"] is None
    assert session.execute(text("SELECT metadata, document_id, size_bytes FROM transfer_events WHERE transfer_id=:id"),
                           {"id": identifier}).one() == ({}, None, None)
    assert client.get("/api/v1/transfers", headers=headers).json()[0]["metadata"] == {}
    assert session.scalar(text("SELECT count(*) FROM documents WHERE document_id=:id"), {"id": document}) == 1
    assert event_count(session, owner) == 1


@pytest.mark.parametrize("changes", [
    {"filename": ""}, {"filename": " \t "}, {"filename": "sensitive-synthetic\n"},
    {"filename": "x" * 513}, {"filename": "\ud800"}, {"filename": 42},
    {"document_id": ""}, {"document_id": " "}, {"document_id": "x" * 129}, {"document_id": "x\x00"},
    {"document_id": "\ud800"}, {"document_id": 42},
    {"size_bytes": -1}, {"size_bytes": 2**63}, {"size_bytes": True}, {"size_bytes": "5"}, {"size_bytes": 1.5},
    {"progress": -1}, {"progress": 101}, {"progress": True}, {"progress": "5"}, {"progress": 1.5},
    {"metadata": None}, {"metadata": []}, {"metadata": "sensitive-synthetic"},
    {"metadata": {"error": "sensitive-synthetic" + "x" * 16384}}, {"metadata": {"bad": "\x00"}},
    {"metadata": {"sensitive-synthetic\x00": "value"}}, {"metadata": {"key": "\ud800"}},
    {"sensitive-synthetic": "secret"}, {"owner_user_id": "43"}, {"metadata_": {}},
    {"direction": "sensitive-synthetic"}, {"status": "sensitive-synthetic"},
])
def test_invalid_create_never_writes(records, changes):
    client, session, headers, owner, _ = records
    # ASCII JSON can represent lone surrogate code points so validation sees them.
    raw = json.dumps({"filename": "synthetic.txt", "direction": "UPLOAD", **changes})
    response = client.post("/api/v1/transfers", headers={**headers, "Content-Type": "application/json"}, content=raw)
    assert_private(response, 422)
    assert event_count(session, owner) == 0
    assert create(client, headers).status_code == 200


@pytest.mark.parametrize("changes", [
    {}, {"progress": None}, {"status": None}, {"metadata": None}, {"size_bytes": -1},
    {"size_bytes": 2**63}, {"size_bytes": True}, {"size_bytes": "5"}, {"progress": True},
    {"progress": 101}, {"progress": "50"}, {"document_id": " "}, {"document_id": "x" * 129},
    {"metadata": {"bad": "\x00"}}, {"metadata": {"sensitive-synthetic": "x" * 16384}},
    {"sensitive-synthetic": "secret"}, {"filename": "sensitive-synthetic"}, {"owner_user_id": "43"}, {"metadata_": {}},
])
def test_invalid_patch_preserves_row_and_session(records, changes):
    client, session, headers, owner, _ = records
    identifier = create(client, headers, metadata={"keep": "synthetic"}).json()["transfer_id"]
    before = session.execute(text("SELECT progress, size_bytes, metadata, updated_at FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}).one()
    response = client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json=changes)
    assert_private(response, 422)
    assert session.execute(text("SELECT progress, size_bytes, metadata, updated_at FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}).one() == before
    assert event_count(session, owner) == 1
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"progress": 10}).status_code == 200


@pytest.mark.parametrize("operation", ["create", "patch"])
def test_metadata_byte_and_depth_boundaries(records, operation):
    client, session, headers, _, _ = records
    identifier = create(client, headers).json()["transfer_id"]

    def request(value):
        if operation == "create":
            return create(client, headers, metadata=value)
        return client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"metadata": value})

    exact = {"x": "é" * 8188}
    assert len(json.dumps(exact, ensure_ascii=False, separators=(",", ":")).encode()) == 16384
    assert request(exact).status_code == 200
    assert_private(request({"x": exact["x"] + "a"}), 422)
    value = "leaf"
    for _ in range(15):
        value = [value]
    assert request({"x": value}).status_code == 200
    assert_private(request({"x": [value]}), 422)
    assert session.scalar(text("SELECT 1")) == 1


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("operation", ["create", "patch"])
def test_nonfinite_json_is_private_and_does_not_write(records, constant, operation):
    client, session, headers, owner, _ = records
    identifier = create(client, headers).json()["transfer_id"]
    prefix = '"filename":"synthetic.txt","direction":"UPLOAD",' if operation == "create" else ""
    raw = '{' + prefix + '"metadata":{"sensitive-synthetic":' + constant + '}}'
    response = client.request("POST" if operation == "create" else "PATCH",
                              "/api/v1/transfers" if operation == "create" else f"/api/v1/transfers/{identifier}",
                              headers={**headers, "Content-Type": "application/json"}, content=raw)
    assert_private(response, 422)
    assert_private(client.get("/api/v1/transfers?limit=sensitive-synthetic", headers=headers), 422)
    assert event_count(session, owner) == 1


@pytest.mark.parametrize("value", ["x" * 129, "sensitive-synthetic\x00", " "])
def test_path_ids_are_validated_before_writing(records, value):
    from urllib.parse import quote
    client, session, headers, owner, _ = records
    response = client.patch("/api/v1/transfers/" + quote(value, safe=""), headers=headers, json={"progress": 1})
    assert_private(response, 422)
    assert event_count(session, owner) == 0


def test_valid_boundaries_preserve_unicode_names_and_bigint(records):
    client, session, headers, _, _ = records
    response = create(client, headers, filename="é" * 512, size_bytes=2**63 - 1, progress=100)
    assert response.status_code == 200
    assert response.json()["filename"] == "é" * 512 and response.json()["size_bytes"] == 2**63 - 1
    identifier = response.json()["transfer_id"]
    assert session.scalar(text("SELECT size_bytes FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}) == 2**63 - 1
    assert client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"progress": 0, "size_bytes": 0}).status_code == 200


def test_request_body_boundary_and_malformed_json_do_not_write(records):
    client, session, headers, owner, _ = records
    body = b'{"filename":"synthetic.txt","direction":"UPLOAD"}'
    body += b" " * (MAX_REQUEST_BYTES - len(body))
    response = client.post("/api/v1/transfers", headers={**headers, "Content-Type": "application/json"}, content=body)
    assert response.status_code == 200
    assert_private(client.post("/api/v1/transfers", headers=headers, content=body + b" "), 413)
    response = client.post("/api/v1/transfers", headers={**headers, "Content-Type": "application/json"},
                           content=b'{"sensitive-synthetic":')
    assert_private(response, 422)
    assert event_count(session, owner) == 1


@pytest.mark.parametrize("declared_length", [None, "1", "999999"])
def test_chunked_body_limit_rejects_actual_bytes_before_route(declared_length):
    from app.interfaces.api.body_limit import RequestBodyLimit
    reached, messages = [], []

    async def downstream(scope, receive, send):
        reached.append(True)

    async def exercise():
        chunks = iter([{"type": "http.request", "body": b"x" * 32768, "more_body": True},
                       {"type": "http.request", "body": b"x" * 32769, "more_body": False}])

        async def receive():
            return next(chunks)

        async def send(message):
            messages.append(message)
        headers = [(b"content-length", declared_length.encode())] if declared_length else []
        await RequestBodyLimit(downstream)({"type": "http", "headers": headers}, receive, send)
    asyncio.run(exercise())
    assert not reached
    assert messages[0]["status"] == 413


def test_openapi_documents_contract(configured_client):
    schema = configured_client[0].get("/openapi.json").json()
    create = schema["components"]["schemas"]["TransferCreateRequest"]
    assert create["additionalProperties"] is False
    assert create["properties"]["filename"]["maxLength"] == 512
    assert {"400", "401", "404", "413", "422", "500"} <= schema["paths"]["/api/v1/transfers"]["post"]["responses"].keys()


@pytest.mark.parametrize("operation,event", [("create", "INSERT"), ("patch", "UPDATE"), ("clear", "DELETE")])
def test_sql_failures_are_private_rollback_and_recover_same_session(records, operation, event):
    client, session, headers, owner, _ = records
    # All trigger DDL belongs to this connection's temporary shadow, never a shared table.
    session.execute(text("CREATE TEMP TABLE transfer_events (LIKE public.transfer_events INCLUDING ALL)"))
    session.commit()
    row = create(client, headers, status="COMPLETED", progress=100)
    assert row.status_code == 200
    identifier = row.json()["transfer_id"]
    session.execute(text("""
        CREATE FUNCTION pg_temp.synthetic_transfer_failure() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'sensitive-synthetic SQL details'; END $$
    """))
    session.execute(text(f"CREATE TRIGGER synthetic_failure BEFORE {event} ON pg_temp.transfer_events FOR EACH ROW EXECUTE FUNCTION pg_temp.synthetic_transfer_failure()"))
    session.commit()

    def request():
        if operation == "create":
            return create(client, headers)
        if operation == "patch":
            return client.patch(f"/api/v1/transfers/{identifier}", headers=headers, json={"size_bytes": 50})
        return client.delete("/api/v1/transfers/history", headers=headers)

    response = request()
    assert_private(response, 500)
    assert response.json() == {"detail": "Database operation failed."}
    assert session.scalar(text("SELECT 1")) == 1
    assert event_count(session, owner) == 1
    assert session.scalar(text("SELECT size_bytes FROM transfer_events WHERE transfer_id=:id"), {"id": identifier}) is None
    session.execute(text("DROP TRIGGER synthetic_failure ON pg_temp.transfer_events"))
    session.commit()
    assert request().status_code == 200


def test_identifier_upper_boundary_and_body_depth_are_controlled(records):
    client, session, headers, owner, _ = records
    identifier = "x" * 128
    session.execute(text("""
        INSERT INTO documents (document_id, owner_user_id, filename, storage_path, mime_type)
        VALUES (:id, :owner, 'synthetic.txt', 'synthetic.txt', 'text/plain')
    """), {"id": identifier, "owner": str(owner)})
    session.commit()
    assert create(client, headers, document_id=identifier).status_code == 200
    assert client.patch("/api/v1/transfers/" + "x" * 128, headers=headers, json={"progress": 1}).status_code == 404
    raw = '{"metadata":' + '[' * 1500 + '0' + ']' * 1500 + '}'
    response = client.post("/api/v1/transfers", headers={**headers, "Content-Type": "application/json"}, content=raw)
    # JSON parser recursion limits can fail before or during request validation.
    assert response.status_code in (400, 422)
    assert_private(response, response.status_code)
    assert event_count(session, owner) == 1
