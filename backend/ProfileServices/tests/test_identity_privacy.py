import hashlib
import io
from time import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.config.database import get_session


@pytest.mark.parametrize(("field", "value"), [
    ("user_id", None), ("user_id", "1"), ("user_id", True), ("user_id", 1.5),
    ("user_id", 0), ("user_id", -1), ("user_id", 2**63), ("user_id", []),
    ("exp", None), ("exp", "9999999999"), ("exp", True), ("exp", 1.5),
    ("exp", 0), ("exp", int(time()) - 100),
    ("iat", None), ("iat", "1"), ("iat", True), ("iat", -1), ("iat", int(time()) + 10000),
    ("jti", None), ("jti", 1), ("jti", ""), ("jti", "x" * 129),
    ("token_type", None), ("token_type", "refresh"), ("token_type", ["access"]),
    ("hash_password", None), ("hash_password", ""), ("hash_password", "z" * 32),
    ("hash_password", []), ("is_superuser", "false"), ("is_superadmin", 1),
    ("is_staff", []), ("groups", "admin"), ("groups", [1]),
    ("permissions", {"*": True}), ("roles", "SUPERADMIN"),
    ("grupos", None), ("permisos", [None]), ("user_permissions", 1),
    ("sub", "different"), ("sub", None), ("sub", 1),
])
def test_malformed_or_expired_claims_rejected(client, token_headers, field, value):
    response = client.get("/api/v1/profile", headers=token_headers(**{field: value}))
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token."}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("missing", ["user_id", "exp", "iat", "jti", "token_type", "hash_password"])
def test_required_claims_and_no_username_fallback(client, profile_id, signing_key, encoded_password, missing):
    payload = {"user_id": int(profile_id), "exp": int(time()) + 300, "iat": int(time()),
               "jti": uuid4().hex, "token_type": "access", "username": profile_id,
               "hash_password": hashlib.md5(encoded_password.encode()).hexdigest().upper()}
    payload.pop(missing)
    token = jwt.encode(payload, signing_key, algorithm="RS256")
    assert client.get("/api/v1/profile", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_optional_subject_must_be_canonical(client, profile_id, token_headers):
    assert client.get("/api/v1/profile", headers=token_headers(sub=profile_id)).status_code == 200
    assert client.get("/api/v1/profile", headers=token_headers(sub="0" + profile_id)).status_code == 401


def test_token_internals_are_not_returned(client, token_headers, encoded_password):
    response = client.get("/api/v1/profile", headers=token_headers())
    assert response.status_code == 200
    assert not {"password", "hash_password", "exp", "iat", "jti", "roles", "tenant_memberships"} & response.json().keys()
    assert hashlib.md5(encoded_password.encode()).hexdigest().upper() not in response.text


def test_wrong_signature_and_algorithm(client, profile_id):
    payload = {"user_id": int(profile_id), "exp": int(time()) + 300, "token_type": "access"}
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tokens = [jwt.encode(payload, key, algorithm="RS256"),
              jwt.encode(payload, "synthetic-secret-that-is-at-least-32-bytes", algorithm="HS256"),
              jwt.encode(payload, "", algorithm="none")]
    for token in tokens:
        assert client.get("/api/v1/profile", headers={"Authorization": "Bearer " + token}).status_code == 401


@pytest.mark.parametrize("change", ["inactive", "deleted", "password", "missing"])
def test_current_identity_and_revocation(client, db_session, profile_id, token_headers, change):
    headers = token_headers()
    assert client.get("/api/v1/profile", headers=headers).status_code == 200
    if change == "inactive":
        db_session.execute(text("UPDATE auth_user SET is_active=FALSE WHERE id=:id"), {"id": int(profile_id)})
    elif change == "deleted":
        db_session.execute(text("DELETE FROM auth_user WHERE id=:id"), {"id": int(profile_id)})
    elif change == "password":
        db_session.execute(text("UPDATE auth_user SET password='synthetic-changed' WHERE id=:id"), {"id": int(profile_id)})
    else:
        headers = token_headers(user_id=2**63 - 1)
    assert client.get("/api/v1/profile", headers=headers).status_code == 401
    assert client.put("/api/v1/profile", headers=headers, json={}).status_code == 401
    image = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(image, format="PNG")
    assert client.post("/api/v1/profile/upload", headers=headers, files={
        "file": ("synthetic.png", image.getvalue(), "image/png"),
    }).status_code == 401
    assert db_session.scalar(text("SELECT count(*) FROM user_profiles WHERE user_id=:id"), {"id": profile_id}) == 0


@pytest.mark.parametrize("role", ["user", "superadmin", "tenant_admin"])
def test_two_owners_cannot_cross_read_or_write(client, db_session, profile_id, other_id, token_headers, role):
    claims = {}
    if role == "superadmin":
        db_session.execute(text("UPDATE auth_user SET is_superuser=TRUE,is_staff=TRUE WHERE id=:id"), {"id": int(profile_id)})
        claims = {"is_superuser": True, "is_superadmin": True, "roles": ["SUPERADMIN"]}
    elif role == "tenant_admin":
        claims = {"tenant_memberships": [{"tenant_id": "synthetic", "role": "TENANT_ADMIN"}]}
    owner = token_headers(**claims)
    other = token_headers(user_id=int(other_id))
    assert client.put("/api/v1/profile", headers=other, json={"email": "other@example.invalid"}).status_code == 200
    assert client.put("/api/v1/profile", headers=owner, json={"email": "owner@example.invalid", "user_id": other_id}).status_code == 200
    assert client.get("/api/v1/profile", headers=owner).json()["email"] == "owner@example.invalid"
    assert client.get("/api/v1/profile", headers=other).json()["email"] == "other@example.invalid"
    for path in ("/api/v1/profiles", "/api/v1/profiles/" + other_id, "/api/v1/profiles/" + profile_id):
        assert client.get(path, headers=owner).status_code == 404
        assert client.put(path, headers=owner, json={"email": "forbidden@example.invalid"}).status_code == 404
    assert client.get("/api/v1/profile", headers=other).json()["email"] == "other@example.invalid"
    # Profile must not update the identity source in Auth.
    assert db_session.scalar(text("SELECT email FROM auth_user WHERE id=:id"), {"id": int(profile_id)}) == ""


def test_identity_database_failure_is_closed_and_sanitized(client, token_headers):
    engine = create_engine("postgresql+psycopg://synthetic:secret@127.0.0.1:1/db", connect_args={"connect_timeout": 1})
    def unavailable_session():
        with Session(engine) as session:
            yield session
    client.app.dependency_overrides[get_session] = unavailable_session
    try:
        response = client.get("/api/v1/profile", headers=token_headers())
        assert response.status_code == 503
        assert response.json() == {"detail": "Profile identity verification is unavailable."}
    finally:
        engine.dispose()
