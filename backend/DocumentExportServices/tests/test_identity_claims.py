from time import time
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.config.database import get_session
from app.main import create_app


def configured(settings, session):
    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


@pytest.mark.parametrize(("field", "value"), [
    ("user_id", None), ("user_id", "1"), ("user_id", True), ("user_id", 1.5),
    ("user_id", 0), ("user_id", -1), ("user_id", 2**63), ("user_id", []),
    ("exp", None), ("exp", "9999999999"), ("exp", True), ("exp", 1.5), ("exp", 0),
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
def test_malformed_claims_never_query_identity(settings, token_headers, field, value):
    session = Mock()
    response = configured(settings, session).get("/api/v1/exports", headers=token_headers(**{field: value}))
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication token."}
    assert response.headers["www-authenticate"] == "Bearer"
    session.scalar.assert_not_called()


@pytest.mark.parametrize("missing", ["user_id", "exp", "iat", "jti", "token_type", "hash_password"])
def test_missing_claims_cannot_fall_back_to_username(settings, token_headers, signing_key, owner, missing):
    token = token_headers()["Authorization"].split()[1]
    payload = jwt.decode(token, options={"verify_signature": False})
    del payload[missing]
    payload["username"] = owner
    session = Mock()
    headers = {"Authorization": "Bearer " + jwt.encode(payload, signing_key, algorithm="RS256")}
    assert configured(settings, session).get("/api/v1/exports", headers=headers).status_code == 401
    session.scalar.assert_not_called()


def test_bad_signatures_and_algorithms(settings, token_headers):
    payload = jwt.decode(token_headers()["Authorization"].split()[1], options={"verify_signature": False})
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    session = Mock()
    for algorithm, key in [("RS256", key), ("HS256", "synthetic-secret-with-at-least-32-bytes"), ("none", "")]:
        token = jwt.encode(payload, key, algorithm=algorithm)
        assert configured(settings, session).get("/api/v1/exports", headers={"Authorization": "Bearer " + token}).status_code == 401
    session.scalar.assert_not_called()


def test_identity_outage_is_sanitized(settings, token_headers):
    session = Mock()
    session.scalar.side_effect = SQLAlchemyError("private-query-and-password")
    response = configured(settings, session).get("/api/v1/exports", headers=token_headers())
    assert response.status_code == 503
    assert response.json() == {"detail": "Export identity verification is unavailable."}
