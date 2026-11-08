
import pytest


def test_openapi_documents_auth_and_multipart(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert set(paths) == {"/api/v1/health", "/api/v1/health/db", "/api/v1/profile",
                          "/api/v1/profile/upload", "/api/v1/profile/avatar"}
    for path, methods in {"/api/v1/profile": ("get", "put"), "/api/v1/profile/upload": ("post",),
                          "/api/v1/profile/avatar": ("get", "delete")}.items():
        assert set(paths[path]) == set(methods)
        for method in methods:
            assert paths[path][method]["security"] == [{"HTTPBearer": []}]
    request_schema = response.json()["components"]["schemas"]["ProfileUpdateRequest"]
    assert "expected_version" in request_schema["required"]
    assert request_schema["additionalProperties"] is False
    assert paths["/api/v1/profile"]["get"]["security"] == [{"HTTPBearer": []}]
    upload = paths["/api/v1/profile/upload"]["post"]
    assert upload["security"] == [{"HTTPBearer": []}]
    assert "multipart/form-data" in upload["requestBody"]["content"]
    form = upload["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert set(form["required"]) == {"file", "expected_version"}
    assert set(paths["/api/v1/profile/avatar"]["get"]["responses"]["200"]["content"]) == {"image/jpeg"}
    assert "security" not in paths["/api/v1/health/db"]["get"]
    assert not any(path.startswith("/api/v1/profiles") for path in paths)


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_local_cors(client, origin):
    response = client.options("/api/v1/profile", headers={
        "Origin": origin, "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_external_cors_denied(client):
    response = client.options("/api/v1/profile", headers={
        "Origin": "https://external.invalid", "Access-Control-Request-Method": "PUT",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_authentication_baseline(client, token_headers):
    assert client.get("/api/v1/profile").status_code == 401
    assert client.get("/api/v1/profile", headers=token_headers(token_type="refresh")).status_code == 401
    assert client.get("/api/v1/profile", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_own_profile_roundtrip(client, token_headers, profile_id, db_session):
    headers = token_headers(groups=["synthetic"], permissions=["synthetic.read"])
    empty = client.get("/api/v1/profile", headers=headers)
    assert empty.status_code == 200 and empty.json()["profile_id"] is None
    assert empty.headers["cache-control"] == "no-store"
    assert empty.json()["user_id"] == profile_id
    response = client.put("/api/v1/profile", headers=headers, json={
        "expected_version": 0,
        "email": "synthetic@example.com", "phone_number": "+56000000000",
        "additional_info": {"bio": "synthetic"},
    })
    assert response.status_code == 200
    saved = response.json()
    assert saved["profile_id"] and saved["created_at"] and saved["updated_at"]
    assert saved["groups"] == ["synthetic"] and saved["permissions"] == ["synthetic.read"]
    updated = client.put("/api/v1/profile", headers=headers, json={"phone_number": "", "expected_version": saved["version"]})
    assert updated.status_code == 200
    assert updated.json()["profile_id"] == saved["profile_id"]
    assert updated.json()["phone_number"] is None
    assert updated.json()["email"] == saved["email"]
    assert client.get("/api/v1/profile", headers=headers).json() == updated.json()


def test_other_profile_denied_for_ordinary_user(client, token_headers):
    assert client.get("/api/v1/profiles/unrelated", headers=token_headers()).status_code == 404
    assert client.put("/api/v1/profiles/unrelated", headers=token_headers(), json={}).status_code == 404
