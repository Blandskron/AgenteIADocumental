import io
import json
from time import time
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import security
from app.config.settings import Settings
from app.config.security import load_current_profile as actual_profile_loader


def profile():
    return {"id": 42, "is_superuser": False, "is_superadmin": False, "is_staff": False,
            "groups": [], "permissions": [], "roles": [], "tenant_memberships": [],
            "active_permissions": [], "active_tenant_id": None, "active_area_id": None, "active_role": None}


def transport(monkeypatch, data=None, error=None):
    opener = Mock()
    if error:
        opener.open.side_effect = error
    else:
        opener.open.return_value = io.BytesIO(json.dumps(data).encode())
    monkeypatch.setattr(security, "build_opener", lambda *args: opener)
    return opener


def test_current_auth_grants_replace_all_stale_token_authority(monkeypatch, tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "identity.pem"
    path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    token = jwt.encode({"user_id": 42, "exp": int(time()) + 60, "token_type": "access",
                        "is_superuser": True, "is_superadmin": True, "roles": ["SUPERADMIN"],
                        "groups": ["old"], "grupos": ["old"], "permissions": ["old"], "permisos": ["old"],
                        "active_permissions": ["*"], "tenant_memberships": [{"tenant_id": "old", "role": "TENANT_ADMIN"}]}, key, algorithm="RS256")
    opener = transport(monkeypatch, profile())
    monkeypatch.setattr(security, "load_current_profile", actual_profile_loader)
    result = security.require_authenticated_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
                                                Settings(database_url="fixture", auth_jwt_public_key_path=str(path)))
    assert not security.is_superadmin_user(result)
    for name in ("groups", "grupos", "permissions", "permisos", "roles", "tenant_memberships", "active_permissions"):
        assert result[name] == []
    assert result["user_id"] == 42
    request = opener.open.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer " + token
    assert opener.open.call_args.kwargs["timeout"] == 5


@pytest.mark.parametrize("status", [401, 403, 500, 302])
def test_disabled_deleted_or_changed_password_and_provider_errors_fail_closed(monkeypatch, status):
    transport(monkeypatch, error=HTTPError("http://fixture", status, "private-error", {}, None))
    with pytest.raises(HTTPException) as error:
        actual_profile_loader("synthetic-token", 42, "http://fixture")
    assert error.value.status_code == (401 if status in (401, 403) else 503)
    assert "private-error" not in error.value.detail


@pytest.mark.parametrize("changed", [{"id": 43}, {"id": True}, {"roles": "SUPERADMIN"},
                                      {"is_superadmin": "false"}, {"tenant_memberships": ["bad"]}])
def test_malformed_or_other_identity_never_authorizes(monkeypatch, changed):
    transport(monkeypatch, {**profile(), **changed})
    with pytest.raises(HTTPException) as error:
        actual_profile_loader("synthetic-token", 42, "http://fixture")
    assert error.value.status_code == 503


def test_timeout_is_private_and_redirect_never_forwards_credentials(monkeypatch):
    transport(monkeypatch, error=URLError("private-timeout"))
    with pytest.raises(HTTPException) as error:
        actual_profile_loader("synthetic-token", 42, "http://fixture")
    assert error.value.status_code == 503
    assert "private-timeout" not in error.value.detail
    assert security.NoIdentityRedirect().redirect_request(None, None, 302, "", {}, "http://other") is None
