import json

import pytest
from sqlalchemy import text


@pytest.mark.parametrize(("field", "value"), [
    ("expected_version", None), ("expected_version", True), ("expected_version", -1),
    ("expected_version", "0"), ("expected_version", 2**63 - 1),
    ("email", "synthetic-invalid"), ("email", 123), ("email", "x" * 255 + "@example.com"),
    ("email", "private@example.com\nsecret"), ("phone_number", "+" + "1" * 33),
    ("phone_number", "secret-phone"), ("phone_number", "---"), ("phone_number", []),
    ("profile_picture_url", "javascript:synthetic-secret"), ("profile_picture_url", "data:image/png,secret"),
    ("profile_picture_url", "https://user:secret@example.com/x.png"),
    ("profile_picture_url", "https://example.com/x#fragment"), ("profile_picture_url", "x" * 2049),
    ("profile_picture_url", "https://example.com/" + "é" * 500), ("profile_picture_url", "http://example.com:0/x"),
    ("additional_info", []), ("additional_info", {"x": "private" * 400}),
    ("additional_info", {"x" * 65: "secret"}), ("additional_info", {"private\x00key": "secret"}),
    ("additional_info", {"x": "\x00"}), ("additional_info", {"x": "\ud800"}),
    ("additional_info", {"full_name": []}), ("additional_info", {"bio": "x" * 2001}),
    ("additional_info", {"x": {"x": {"x": {"x": {"x": 1}}}}}),
    ("additional_info", {str(i): i for i in range(65)}),
    ("additional_info", {"x": list(range(256))}),
    ("additional_info", {str(i): "é" * 2048 for i in range(8)}),
])
def test_invalid_fields_never_reflect_values(client, token_headers, field, value):
    body = {"expected_version": 0, "email": "synthetic@example.com", field: value}
    try:
        content = json.dumps(body, ensure_ascii=False).encode()
    except UnicodeEncodeError:
        content = json.dumps(body).encode()
    response = client.put("/api/v1/profile", headers={**token_headers(), "Content-Type": "application/json"}, content=content)
    assert response.status_code == 422
    assert all(set(error) == {"loc", "msg", "type"} for error in response.json()["detail"])
    assert "synthetic@example.com" not in response.text and "private" not in response.text
    assert "secret" not in response.text and "ctx" not in response.text


def test_missing_version_unknown_fields_and_empty_patch(client, token_headers):
    for payload in ({"email": None}, {"expected_version": 0}, {"expected_version": 0, "secret-key": "private"}):
        response = client.put("/api/v1/profile", headers=token_headers(), json=payload)
        assert response.status_code == 422
        assert "secret-key" not in response.text and "private" not in response.text


def test_omission_null_empty_and_metadata_replacement(client, token_headers, db_session, profile_id):
    headers = token_headers()
    assert client.get("/api/v1/profile", headers=headers).json()["version"] == 0
    created = client.put("/api/v1/profile", headers=headers, json={
        "expected_version": 0, "email": " synthetic@EXAMPLE.COM ", "phone_number": "+56 123 456",
        "profile_picture_url": None, "additional_info": {"a": 1, "b": 2},
    })
    assert created.status_code == 200
    assert created.json()["version"] == 1 and created.json()["email"] == "synthetic@example.com"
    cleared = client.put("/api/v1/profile", headers=headers, json={
        "expected_version": 1, "email": None, "phone_number": " ", "additional_info": {"a": 3},
    })
    assert cleared.status_code == 200
    assert cleared.json()["email"] is None and cleared.json()["phone_number"] is None
    assert cleared.json()["profile_picture_url"] == created.json()["profile_picture_url"]
    assert cleared.json()["additional_info"] == {"a": 3} and cleared.json()["version"] == 2
    result = client.put("/api/v1/profile", headers=headers, json={
        "expected_version": 2, "additional_info": None, "profile_picture_url": None,
    })
    assert result.status_code == 200 and result.json()["version"] == 3
    assert result.json()["additional_info"] == {} and result.json()["profile_picture_url"] is None
    assert db_session.scalar(text("SELECT count(*) FROM user_profiles WHERE user_id=:id"), {"id": profile_id}) == 1


def test_stale_version_preserves_saved_profile(client, token_headers):
    headers = token_headers()
    first = client.put("/api/v1/profile", headers=headers, json={"expected_version": 0, "additional_info": {"a": 1}})
    assert first.status_code == 200
    for expected in (0, 5):
        conflict = client.put("/api/v1/profile", headers=headers, json={"expected_version": expected, "additional_info": {"a": 2}})
        assert conflict.status_code == 409
        assert client.get("/api/v1/profile", headers=headers).json() == first.json()


def test_json_byte_limit_including_chunked_streams(client, token_headers):
    headers = {**token_headers(), "Content-Type": "application/json", "Content-Length": "1"}
    body = b'{"expected_version":0,"email":null}'
    padded = body + b" " * (65536 - len(body))
    assert client.put("/api/v1/profile", headers=headers, content=iter([padded[:50], padded[50:], b" "])).status_code == 413
    headers.pop("Content-Length")
    assert client.put("/api/v1/profile", headers=headers, content=iter([padded[:50], padded[50:]])).status_code == 200


@pytest.mark.parametrize("content", [b'{"private":', b'{"email":"\xff"}', b"[" * 2000 + b"]" * 2000], ids=["syntax", "encoding", "depth"])
def test_malformed_json_and_extreme_nesting(client, token_headers, content):
    response = client.put("/api/v1/profile", headers={**token_headers(), "Content-Type": "application/json"}, content=content)
    assert response.status_code == 400 and response.json() == {"detail": "Invalid profile JSON."}


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_metadata_rejected(client, token_headers, value):
    response = client.put("/api/v1/profile", headers={**token_headers(), "Content-Type": "application/json"},
                          content='{"expected_version":0,"additional_info":{"number":' + value + '}}')
    assert response.status_code == 422


def test_metadata_exact_utf8_size_limit(client, token_headers):
    # {"x":"..."} uses eight JSON bytes in addition to the value.
    metadata = {str(i): "x" * 2000 for i in range(8)}
    assert len(json.dumps(metadata, separators=(",", ":")).encode()) < 16384
    assert client.put("/api/v1/profile", headers=token_headers(), json={"expected_version": 0, "additional_info": metadata}).status_code == 200


@pytest.mark.parametrize(("kind", "status"), [("integrity", 409), ("database", 503), ("application", 500)])
def test_persistence_faults_do_not_reflect_details(client, token_headers, monkeypatch, kind, status):
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError
    from app.shared.errors import AppError

    def failure(*args, **kwargs):
        if kind == "integrity":
            raise IntegrityError("private-query", {"email": "secret@example.com"}, RuntimeError("private-database"))
        if kind == "database":
            raise SQLAlchemyError("private-database")
        raise AppError("private-application")
    monkeypatch.setattr("app.infrastructure.database.repositories.profile_repository_pg.UserProfileRepositoryPg.create_or_update", failure)
    response = client.put("/api/v1/profile", headers=token_headers(), json={"expected_version": 0, "email": None})
    assert response.status_code == status and "private" not in response.text and "secret" not in response.text


def test_body_limit_under_proxy_root(settings):
    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app(settings), root_path="/proxy") as configured:
        assert configured.put("/proxy/api/v1/profile", content=b"x" * 65537).status_code == 413
