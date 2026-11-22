from __future__ import annotations

import pytest

from app.config.identity_verifier import (
    IdentityServiceUnavailableError,
    IdentityUnauthorizedError,
    LiveIdentityVerifier,
)


def test_live_identity_verifier_caches_active_user_and_fails_closed() -> None:
    calls = {"count": 0}

    def ok_transport(_url, headers, _timeout):
        calls["count"] += 1
        assert headers["Authorization"] == "Bearer synthetic.jwt.ok"
        return 200, {"id": "u-99", "active_tenant_id": "tenant-z", "is_active": True, "is_superuser": False}

    verifier = LiveIdentityVerifier(ttl_seconds=30.0, transport=ok_transport)
    first = verifier.verify(raw_token="synthetic.jwt.ok", auth_identity_url="http://auth-service:8000/api/users/me/")
    second = verifier.verify(raw_token="synthetic.jwt.ok", auth_identity_url="http://auth-service:8000/api/users/me/")
    assert first["user_id"] == "u-99"
    assert second["active_tenant_id"] == "tenant-z"
    assert calls["count"] == 1  # Cached

    # Revoked token -> 401
    revoked_verifier = LiveIdentityVerifier(transport=lambda *_a: (401, {"detail": "Invalid token"}))
    with pytest.raises(IdentityUnauthorizedError) as exc_401:
        revoked_verifier.verify(raw_token="revoked.jwt", auth_identity_url="http://auth-service:8000/api/users/me/")
    assert exc_401.value.status_code == 401

    # Disabled account -> 403
    disabled_verifier = LiveIdentityVerifier(transport=lambda *_a: (200, {"id": "u-1", "is_active": False}))
    with pytest.raises(IdentityUnauthorizedError) as exc_403:
        disabled_verifier.verify(raw_token="disabled.jwt", auth_identity_url="http://auth-service:8000/api/users/me/")
    assert exc_403.value.status_code == 403

    # AuthServices unreachable -> 503
    down_verifier = LiveIdentityVerifier(transport=lambda *_a: (_ for _ in ()).throw(ConnectionError("refused")))
    with pytest.raises(IdentityServiceUnavailableError):
        down_verifier.verify(raw_token="any.jwt", auth_identity_url="http://auth-service:8000/api/users/me/")
