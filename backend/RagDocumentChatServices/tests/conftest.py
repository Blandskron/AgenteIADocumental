import jwt as identity_fixture_jwt
import pytest as identity_fixture_pytest


# Existing isolated API/SQL tests use synthetic signers rather than the live Auth service.
# test_current_identity exercises the actual transport; release demo uses real Auth.


@identity_fixture_pytest.fixture(autouse=True)
def isolated_identity_provider(monkeypatch):
    def current(token, identifier, url):
        payload = identity_fixture_jwt.decode(token, options={"verify_signature": False})
        return {"id": identifier, "groups": payload.get("groups", []), "permissions": payload.get("permissions", []), **payload}
    monkeypatch.setattr("app.config.security.load_current_profile", current)
