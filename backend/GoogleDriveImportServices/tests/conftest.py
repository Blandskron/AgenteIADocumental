import os
from datetime import UTC, datetime
from hashlib import md5
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config.settings import Settings
from app.main import create_app


@pytest.fixture(scope="session")
def signing_keys(tmp_path_factory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = tmp_path_factory.mktemp("keys") / "public.pem"
    public.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    return key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()), public


@pytest.fixture
def settings(signing_keys):
    return Settings(database_url="postgresql+psycopg://synthetic@127.0.0.1:1/test",
                    auth_jwt_public_key_path=signing_keys[1])


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("DRIVE_TEST_DATABASE_URL")
    if not url:
        pytest.fail("An explicit synthetic DRIVE_TEST_DATABASE_URL is required")
    db = create_engine(url, hide_parameters=True, pool_pre_ping=True)
    yield db
    db.dispose()


@pytest.fixture
def identities(engine):
    marker = uuid4().hex
    ids = []
    tenant = None
    with engine.begin() as c:
        for suffix in ("owner", "other"):
            ids.append(c.scalar(text("""INSERT INTO auth_user
                (username,password,first_name,last_name,email,is_superuser,is_staff,is_active,date_joined)
                VALUES(:name,:password,'','','',false,false,true,now()) RETURNING id"""),
                {"name": "drive-test-" + marker + suffix, "password": "synthetic-" + marker}))
        tenant = c.scalar(text("INSERT INTO tenants(name) VALUES(:name) RETURNING tenant_id"), {"name": marker})
        group = c.scalar(text("INSERT INTO tenant_groups(tenant_id,name) VALUES(:tenant,:name) RETURNING group_id"),
                         {"tenant": tenant, "name": marker})
        c.execute(text("INSERT INTO tenant_group_permissions(group_id,permission_code) VALUES(:g,'use_google_drive')"), {"g": group})
        for identifier in ids:
            c.execute(text("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES(:t,:u,'USER')"), {"t": tenant, "u": str(identifier)})
            c.execute(text("INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES(:t,:u,:g)"),
                      {"t": tenant, "u": str(identifier), "g": group})
    result = {"owner": ids[0], "other": ids[1], "tenant": tenant, "group": group,
              "fingerprint": md5(("synthetic-" + marker).encode()).hexdigest().upper()}
    try:
        yield result
    finally:
        with engine.begin() as c:
            c.execute(text("DELETE FROM google_drive_import_files WHERE import_id IN (SELECT import_id FROM google_drive_imports WHERE owner_user_id=ANY(:ids))"), {"ids": list(map(str,ids))})
            c.execute(text("DELETE FROM google_drive_imports WHERE owner_user_id=ANY(:ids)"), {"ids": list(map(str,ids))})
            c.execute(text("DELETE FROM google_drive_oauth_attempts WHERE owner_user_id=ANY(:ids)"), {"ids": list(map(str,ids))})
            c.execute(text("DELETE FROM google_drive_connections WHERE owner_user_id=ANY(:ids)"), {"ids": list(map(str,ids))})
            c.execute(text("DELETE FROM tenants WHERE tenant_id=:t"), {"t": tenant})
            c.execute(text("DELETE FROM auth_user WHERE id=ANY(:ids)"), {"ids": ids})


@pytest.fixture
def token(signing_keys, identities):
    def make(**changes):
        now = int(datetime.now(UTC).timestamp())
        claims = {"user_id": identities["owner"], "hash_password": identities["fingerprint"], "active_tenant_id": identities["tenant"],
                  "iat": now, "exp": now + 300, "jti": uuid4().hex, "token_type": "access"}
        claims.update(changes)
        return {"Authorization": "Bearer " + jwt.encode(claims, signing_keys[0], algorithm="RS256")}
    return make


@pytest.fixture
def runtime_url():
    url = make_url(os.environ["DRIVE_TEST_DATABASE_URL"])
    return url.set(username="drive_runtime", password=os.environ["DRIVE_TEST_RUNTIME_PASSWORD"]).render_as_string(hide_password=False)


@pytest.fixture
def client(runtime_url, signing_keys):
    settings = Settings(database_url=runtime_url, auth_jwt_public_key_path=signing_keys[1])
    app = create_app(settings)
    with TestClient(app) as value:
        yield value
    assert app.state.database._engine is None
