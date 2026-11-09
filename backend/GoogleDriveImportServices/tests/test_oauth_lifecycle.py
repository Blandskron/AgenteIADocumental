import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.application.use_cases.manage_google_drive_imports import ManageGoogleDriveImports
from app.config.security import DriveUser
from app.config.settings import Settings
from app.infrastructure.database.connection import Database
from app.infrastructure.database.repositories.google_drive_repository_pg import GoogleDriveRepository
from app.infrastructure.google.drive_client import GoogleDriveClient
from app.infrastructure.google.token_cipher import TokenCipher
from app.main import create_app
from app.shared.errors import DriveConflictError, GoogleDriveError, ReauthorizationRequired, ValidationError

VERIFIER = "v" * 43
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
SCOPE = "https://www.googleapis.com/auth/drive.file"


class Provider:
    def __init__(self):
        self.calls = []
        self.subject = "synthetic-account"
        self.payload = {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh",
                        "token_type": "Bearer", "expires_in": 3600, "scope": SCOPE}
        self.failure = None

    def build_authorization_url(self, state, challenge):
        return "https://accounts.google.com/?state=" + state

    def exchange_code(self, code, verifier):
        self.calls.append("exchange")
        if self.failure:
            raise self.failure
        return dict(self.payload)

    def refresh_access_token(self, token):
        self.calls.append("refresh")
        if self.failure:
            raise self.failure
        return dict(self.payload)

    def get_userinfo(self, token):
        self.calls.append("identity")
        return {"permissionId": self.subject, "emailAddress": "synthetic@example.invalid"}

    def revoke(self, token):
        self.calls.append("revoke")
        if self.failure:
            raise self.failure


@pytest.fixture
def lifecycle(runtime_url, signing_keys, identities):
    settings = Settings(database_url=runtime_url, auth_jwt_public_key_path=signing_keys[1],
                        google_drive_enabled=True, google_oauth_client_id="synthetic-client",
                        google_oauth_client_secret="synthetic-secret", google_token_encryption_key="a" * 48)
    database = Database(runtime_url)
    user = DriveUser(str(identities["owner"]), identities["fingerprint"], identities["tenant"])
    repo = GoogleDriveRepository(database, user)
    provider = Provider()
    use_case = ManageGoogleDriveImports(repo, provider, None, TokenCipher.from_settings(settings), settings)
    try:
        yield SimpleNamespace(service=use_case, repo=repo, provider=provider, settings=settings, database=database, user=user)
    finally:
        database.close()


def authorize(context):
    attempt = context.service.auth_url(context.user.user_id, CHALLENGE)
    return context.service.connect(context.user.user_id, "synthetic-code", attempt["state"], VERIFIER)


@pytest.mark.postgres
@pytest.mark.parametrize("mutation", ["missing", "wrong_verifier", "other_owner", "tenant", "expired", "configuration"])
def test_invalid_attempt_does_not_contact_provider(lifecycle, engine, identities, mutation):
    context = lifecycle
    attempt = context.service.auth_url(context.user.user_id, CHALLENGE)
    state, verifier = attempt["state"], VERIFIER
    if mutation == "missing":
        state = "x" * 43
    if mutation == "wrong_verifier":
        verifier = "x" * 43
    if mutation in {"other_owner", "tenant"}:
        context.repo._user = DriveUser(str(identities["other"]) if mutation == "other_owner" else context.user.user_id,
                                      context.user.fingerprint, None if mutation == "tenant" else context.user.tenant_id)
        if mutation == "tenant":
            # Keep the alternate identity authorized but prove the attempt binding is different.
            with engine.begin() as c:
                c.execute(text("UPDATE auth_user SET is_superuser=true WHERE id=:id"), {"id": identities["owner"]})
    if mutation == "expired":
        with engine.begin() as c:
            c.execute(text("UPDATE google_drive_oauth_attempts SET expires_at=now()-interval '1 second' WHERE owner_user_id=:u"), {"u": context.user.user_id})
    if mutation == "configuration":
        context.settings.google_oauth_client_id = "changed-client"
    with pytest.raises(ValidationError):
        context.service.connect(context.user.user_id, "synthetic-code", state, verifier)
    assert context.provider.calls == []


@pytest.mark.postgres
def test_consumption_is_atomic_and_state_is_never_stored_raw(lifecycle, engine):
    context = lifecycle
    state = context.service.auth_url(context.user.user_id, CHALLENGE)["state"]
    with engine.begin() as c:
        row = c.execute(text("SELECT state_hash,code_challenge FROM google_drive_oauth_attempts WHERE owner_user_id=:u"), {"u": context.user.user_id}).one()
        assert row.state_hash == hashlib.sha256(state.encode()).hexdigest()
        assert row.code_challenge != VERIFIER
    def consume(_):
        try:
            return context.repo.consume_attempt(state, CHALLENGE, context.service._configuration_hash())
        except (ValidationError, DriveConflictError):
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, range(2)))
    assert sum(result is not None for result in results) == 1
    context.repo.fail_credentials(next(result for result in results if result), "DISCONNECTED")
    with pytest.raises(ValidationError):
        context.repo.consume_attempt(state, CHALLENGE, context.service._configuration_hash())


@pytest.mark.postgres
def test_reconnect_omitted_refresh_only_preserves_same_account(lifecycle):
    context = lifecycle
    first = authorize(context)
    assert first["connected"] and first["provider_account_id"] == context.provider.subject
    assert "synthetic-access" not in str(first) and "synthetic-refresh" not in str(first)
    old = context.repo.get_connection(context.user.user_id)
    context.provider.payload.pop("refresh_token")
    second = authorize(context)
    assert second["version"] > first["version"]
    assert context.repo.get_connection(context.user.user_id).refresh_token_encrypted == old.refresh_token_encrypted
    context.provider.subject = "another-account"
    with pytest.raises(ReauthorizationRequired):
        authorize(context)
    retained = context.repo.get_connection(context.user.user_id)
    assert retained.provider_account_id == old.provider_account_id and retained.grant_status == "ACTIVE"
    context.provider.subject = old.provider_account_id
    context.settings.google_oauth_client_id = "another-client"
    with pytest.raises(ReauthorizationRequired):
        authorize(context)
    retained = context.repo.get_connection(context.user.user_id)
    assert retained.oauth_client_id == old.oauth_client_id and retained.refresh_token_encrypted == old.refresh_token_encrypted


@pytest.mark.postgres
@pytest.mark.parametrize("failure", [GoogleDriveError("synthetic-invalid-grant"), httpx.ReadTimeout("synthetic-timeout")])
def test_refresh_ambiguity_requires_reauthorization_without_losing_ciphertext(lifecycle, engine, failure):
    context = lifecycle
    authorize(context)
    with engine.begin() as c:
        c.execute(text("UPDATE google_drive_connections SET expires_at=now() WHERE owner_user_id=:u"), {"u": context.user.user_id})
    old = context.repo.get_connection(context.user.user_id)
    context.provider.failure = failure
    with pytest.raises(type(failure)):
        context.service._valid_access_token(context.user.user_id, old)
    stored = context.repo.get_connection(context.user.user_id)
    assert stored.grant_status == "REAUTH_REQUIRED" and stored.refresh_token_encrypted == old.refresh_token_encrypted
    with pytest.raises(DriveConflictError):
        context.service._valid_access_token(context.user.user_id, stored)
    assert context.provider.calls.count("refresh") == 1


@pytest.mark.postgres
def test_refresh_serialization_and_late_completion_cannot_overwrite(lifecycle, engine):
    context = lifecycle
    status = authorize(context)
    lease = context.repo.claim_credentials(status["version"], "REFRESH")
    with pytest.raises(DriveConflictError):
        context.repo.claim_credentials(status["version"], "REFRESH")
    with engine.begin() as c:
        c.execute(text("UPDATE google_drive_connections SET lease_until=now()-interval '1 second' WHERE owner_user_id=:u"), {"u": context.user.user_id})
    with pytest.raises(DriveConflictError):
        context.repo.claim_credentials(status["version"], "REFRESH")
    with pytest.raises(DriveConflictError):
        context.repo.finish_credentials(lease, {"grant_status": "ACTIVE"})
    assert context.repo.get_connection(context.user.user_id).grant_status == "REAUTH_REQUIRED"


@pytest.mark.postgres
def test_refresh_success_keeps_omitted_refresh_and_advances_version(lifecycle, engine):
    context = lifecycle
    status = authorize(context)
    with engine.begin() as c:
        c.execute(text("UPDATE google_drive_connections SET expires_at=now() WHERE owner_user_id=:u"), {"u": context.user.user_id})
    connection = context.repo.get_connection(context.user.user_id)
    previous_refresh = connection.refresh_token_encrypted
    context.provider.payload.pop("refresh_token")
    assert context.service._valid_access_token(context.user.user_id, connection) == "synthetic-access"
    assert connection.version > status["version"]
    assert context.repo.get_connection(context.user.user_id).refresh_token_encrypted == previous_refresh


@pytest.mark.postgres
def test_failed_revocation_blocks_reconnect_then_retry_removes_credentials(lifecycle):
    context = lifecycle
    first = authorize(context)
    context.provider.failure = httpx.ReadTimeout("synthetic-timeout")
    pending = context.service.disconnect(context.user.user_id, first["version"])
    assert pending["grant_status"] == "REVOKE_PENDING" and not pending["connected"]
    assert context.repo.get_connection(context.user.user_id).refresh_token_encrypted
    with pytest.raises(DriveConflictError):
        context.service.auth_url(context.user.user_id, CHALLENGE)
    context.provider.failure = None
    disconnected = context.service.disconnect(context.user.user_id, pending["version"])
    assert disconnected["grant_status"] == "DISCONNECTED"
    row = context.repo.get_connection(context.user.user_id)
    assert row.access_token_encrypted == "" and row.refresh_token_encrypted is None
    with pytest.raises(DriveConflictError):
        context.repo.ensure_connection_current(first["version"])


@pytest.mark.postgres
def test_http_contract_validates_before_provider_and_hides_credentials(lifecycle, token, monkeypatch):
    context = lifecycle
    monkeypatch.setattr(GoogleDriveClient, "exchange_code", lambda self, code, verifier: context.provider.exchange_code(code, verifier))
    monkeypatch.setattr(GoogleDriveClient, "get_userinfo", lambda self, token: context.provider.get_userinfo(token))
    with TestClient(create_app(context.settings)) as client:
        headers = token()
        assert client.get("/api/v1/google-drive/auth-url", headers=headers).status_code == 410
        assert client.post("/api/v1/google-drive/oauth/callback", headers=headers, json={"code": "synthetic-code"}).status_code == 422
        attempt = client.post("/api/v1/google-drive/auth-url", headers=headers, json={"code_challenge": CHALLENGE})
        assert attempt.status_code == 200
        query = parse_qs(urlsplit(attempt.json()["authorization_url"]).query)
        assert query["code_challenge_method"] == ["S256"] and query["code_challenge"] == [CHALLENGE]
        payload = {"code": "synthetic-code", "state": attempt.json()["state"], "code_verifier": VERIFIER}
        assert client.post("/api/v1/google-drive/oauth/callback", headers=headers, json={**payload, "issuer": "https://evil.invalid"}).status_code == 422
        success = client.post("/api/v1/google-drive/oauth/callback", headers=headers, json=payload)
        assert success.status_code == 200 and success.json()["connected"]
        assert "encrypted" not in success.text and "synthetic-access" not in success.text
        assert client.post("/api/v1/google-drive/oauth/callback", headers=headers, json=payload).status_code in {400, 409}
        assert context.provider.calls == ["exchange", "identity"]
        assert success.headers["cache-control"] == "no-store, private"
        oversized = client.post("/api/v1/google-drive/oauth/callback", headers=headers, content=b"x" * 16385)
        assert oversized.status_code == 413 and context.provider.calls == ["exchange", "identity"]


@pytest.mark.postgres
def test_attempt_budget_and_missing_offline_grant_preserve_disconnected_state(lifecycle):
    context = lifecycle
    context.provider.payload.pop("refresh_token")
    with pytest.raises(ReauthorizationRequired):
        authorize(context)
    assert context.service.connected_status(context.user.user_id)["grant_status"] == "DISCONNECTED"
    for _ in range(10):
        context.service.auth_url(context.user.user_id, CHALLENGE)
    with pytest.raises(DriveConflictError):
        context.service.auth_url(context.user.user_id, CHALLENGE)


def test_versioned_cipher_rotation_and_unknown_or_legacy_keys_fail_closed():
    first = TokenCipher("a" * 48, "old")
    encrypted = first.encrypt("synthetic-credential")
    rotated = TokenCipher("b" * 48, "new", {"old": "a" * 48})
    assert rotated.decrypt(encrypted) == "synthetic-credential"
    replacement = rotated.encrypt(rotated.decrypt(encrypted))
    assert replacement.startswith("drive1.new.")
    assert TokenCipher("b" * 48, "new").decrypt(replacement) == "synthetic-credential"
    with pytest.raises(ReauthorizationRequired):
        TokenCipher("b" * 48, "new").decrypt(encrypted)
    legacy = first._keys["old"].encrypt(b"synthetic-legacy").decode()
    with pytest.raises(ReauthorizationRequired):
        rotated.decrypt(legacy)
    assert TokenCipher("b" * 48, "new", {"old": "a" * 48}, "old").decrypt(legacy) == "synthetic-legacy"


@pytest.mark.parametrize("payload", [None, {}, {"access_token": "bad\r\nvalue"}, {"expires_in": True}, {"scope": "openid"}])
def test_provider_token_contract_is_strict(settings, payload):
    service = ManageGoogleDriveImports(None, None, None, TokenCipher("a" * 48), settings)
    response = {"access_token": "synthetic", "token_type": "Bearer", "expires_in": 3600}
    if isinstance(payload, dict):
        response.update(payload)
    if payload in (None, {}):
        response = payload
    with pytest.raises(ValidationError):
        service._credential_values(response)


@pytest.mark.postgres
def test_reviewed_rotation_is_atomic_and_replay_is_rejected(lifecycle, engine):
    import importlib.util
    spec = importlib.util.spec_from_file_location("rotate_credentials", "/drive-checks/rotate_credentials.py")
    rotation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rotation)
    context = lifecycle
    authorize(context)
    cipher = TokenCipher("b" * 48, "new", {"v1": "a" * 48})
    with engine.begin() as c:
        plan = rotation.plan_rotation(c, cipher)
    assert len(plan["entries"]) == 1 and plan["entries"][0]["outcome"] == "ready"
    assert "synthetic-access" not in str(plan) and "drive1." not in str(plan)
    with engine.begin() as c:
        assert rotation.apply_rotation(c, cipher, plan) == 1
    stored = context.repo.get_connection(context.user.user_id)
    assert stored.grant_status == "ACTIVE" and stored.provider_account_id == context.provider.subject
    assert cipher.decrypt(stored.access_token_encrypted) == "synthetic-access"
    with pytest.raises(ValueError), engine.begin() as c:
        rotation.apply_rotation(c, cipher, plan)
    assert context.repo.get_connection(context.user.user_id).version == stored.version


def test_google_transport_uses_pkce_drive_identity_and_explicit_revocation(settings, monkeypatch):
    from urllib.parse import parse_qs
    settings.google_oauth_client_id = "synthetic-client"
    settings.google_oauth_client_secret = "synthetic-secret"
    seen = []
    real_client = httpx.Client

    def wire(payload, status=200):
        import json
        return httpx.Response(status, stream=httpx.ByteStream(json.dumps(payload).encode()))

    def transport(request):
        seen.append(request)
        if request.url.path == "/token":
            form = parse_qs(request.content.decode())
            assert form["code_verifier"] == [VERIFIER]
            assert form["redirect_uri"] == [settings.google_oauth_redirect_uri]
            return wire({"access_token": "synthetic"})
        if request.url.path == "/drive/v3/about":
            assert request.url.params["fields"] == "user(permissionId,emailAddress)"
            return wire({"user": {"permissionId": "synthetic-account"}})
        if request.url.path == "/revoke":
            return wire({"error": "invalid_token"}, 400)
        raise AssertionError("Unexpected external request")

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs))
    client = GoogleDriveClient(settings)
    assert client.exchange_code("synthetic-code", VERIFIER)["access_token"] == "synthetic"
    assert client.get_userinfo("synthetic")["permissionId"] == "synthetic-account"
    client.revoke("synthetic-refresh")
    assert [request.url.host for request in seen] == ["oauth2.googleapis.com", "www.googleapis.com", "oauth2.googleapis.com"]
