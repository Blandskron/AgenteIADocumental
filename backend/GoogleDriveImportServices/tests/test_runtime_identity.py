from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.config.security import DriveUser
from app.infrastructure.database.connection import Database
from app.infrastructure.database.repositories.google_drive_repository_pg import GoogleDriveRepository

pytestmark = pytest.mark.postgres


def test_disabled_runtime_and_own_history(client, token, identities, engine):
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health/db").json() == {"status":"ok","enabled":False}
    headers = token()
    assert client.get("/api/v1/google-drive/connection",headers=headers).json()["connected"] is False
    assert client.get("/api/v1/google-drive/imports",headers=headers).json() == []
    assert client.get("/api/v1/google-drive/auth-url",headers=headers).status_code == 503
    assert client.post("/api/v1/google-drive/oauth/callback",json={"code":"synthetic"},headers=headers).status_code == 503
    assert client.post("/api/v1/google-drive/imports",json={"files":[{"file_id":"synthetic"}]},headers=headers).status_code == 503
    with engine.begin() as c:
        identifier = c.scalar(text("INSERT INTO google_drive_imports(owner_user_id) VALUES(:owner) RETURNING import_id"),
                              {"owner":str(identities["other"])})
    assert client.get("/api/v1/google-drive/imports/"+identifier,headers=headers).status_code == 404
    assert client.get("/api/v1/google-drive/imports/"+identifier+"/files",headers=headers).status_code == 404
    assert client.get("/api/v1/google-drive/imports",headers=token(token_type="refresh")).status_code == 401
    assert client.get("/api/v1/google-drive/imports").status_code == 401


@pytest.mark.parametrize("change",[{"user_id":True},{"user_id":"42"},{"user_id":0},{"hash_password":"bad"},
    {"exp":True},{"iat":-1},{"jti":""},{"sub":"wrong"},{"active_tenant_id":42},{"is_superuser":"true"}])
def test_malformed_signed_identity_is_rejected(client, token, change):
    assert client.get("/api/v1/google-drive/imports",headers=token(**change)).status_code == 401


@pytest.mark.parametrize("claim",["exp","iat","jti","user_id","hash_password","token_type"])
def test_missing_claim_is_rejected(client, token, signing_keys, claim):
    headers = token()
    payload = jwt.decode(headers["Authorization"].split()[1], options={"verify_signature":False})
    payload.pop(claim)
    headers["Authorization"] = "Bearer " + jwt.encode(payload,signing_keys[0],algorithm="RS256")
    assert client.get("/api/v1/google-drive/imports",headers=headers).status_code == 401


@pytest.mark.parametrize("mutation",["password","inactive","delete"])
def test_real_database_revocation(client, token, engine, identities, mutation):
    headers=token()
    assert client.get("/api/v1/google-drive/imports",headers=headers).status_code == 200
    with engine.begin() as c:
        query={"password":"UPDATE auth_user SET password='changed' WHERE id=:id",
               "inactive":"UPDATE auth_user SET is_active=false WHERE id=:id",
               "delete":"DELETE FROM auth_user WHERE id=:id"}[mutation]
        c.execute(text(query),{"id":identities["owner"]})
    assert client.get("/api/v1/google-drive/imports",headers=headers).status_code == 401


@pytest.mark.parametrize("mutation",["permission","membership","tenant","foreign_group"])
def test_current_tenant_permission_not_stale_claims(client, token, engine, identities, mutation):
    headers=token(active_permissions=["*"],is_superuser=True,roles=["SUPERADMIN"])
    with engine.begin() as c:
        queries={"permission":"DELETE FROM tenant_group_permissions WHERE group_id=:g",
                 "membership":"UPDATE tenant_memberships SET status='DISABLED' WHERE tenant_id=:t",
                 "tenant":"UPDATE tenants SET status='DISABLED' WHERE tenant_id=:t",
                 "foreign_group":"UPDATE tenant_user_groups SET tenant_id='invalid-tenant' WHERE group_id=:g"}
        # The FK itself blocks a non-existing tenant, so instead remove the user's group membership.
        if mutation=="foreign_group":
            queries[mutation]="DELETE FROM tenant_user_groups WHERE user_id=:u"
        c.execute(text(queries[mutation]),{"g":identities["group"],"t":identities["tenant"],"u":str(identities["owner"])})
    assert client.get("/api/v1/google-drive/imports",headers=headers).status_code == 403
    assert client.get("/api/v1/google-drive/imports",headers=token(active_tenant_id="wrong")).status_code == 403


def test_database_superuser_authority_and_immediate_demotion(client, token, engine, identities):
    with engine.begin() as c:
        c.execute(text("UPDATE auth_user SET is_superuser=true WHERE id=:id"),{"id":identities["owner"]})
        c.execute(text("DELETE FROM tenant_user_groups WHERE user_id=:id"),{"id":str(identities["owner"])})
    headers=token(active_tenant_id=None)
    assert client.get("/api/v1/google-drive/imports",headers=headers).status_code == 200
    with engine.begin() as c:
        c.execute(text("UPDATE auth_user SET is_superuser=false WHERE id=:id"),{"id":identities["owner"]})
    assert client.get("/api/v1/google-drive/imports",headers=headers).status_code == 403


def test_revalidation_between_operations_without_network_lock(runtime_url, identities, engine):
    user=DriveUser(str(identities["owner"]),identities["fingerprint"],identities["tenant"])
    database=Database(runtime_url)
    repo=GoogleDriveRepository(database,user)
    try:
        repo.check_identity()
        # This update would block if the guard kept its FOR SHARE lock after returning.
        with engine.begin() as c:
            c.execute(text("SET LOCAL lock_timeout='1s'"))
            c.execute(text("UPDATE auth_user SET password='changed' WHERE id=:id"),{"id":identities["owner"]})
        with pytest.raises(HTTPException) as failure:
            repo.get_connection(user.user_id)
        assert failure.value.status_code==401
    finally:
        database.close()


@pytest.mark.parametrize("statement",[
    "SELECT password FROM auth_user","SELECT * FROM documents","SELECT * FROM document_folders",
    "UPDATE auth_user SET is_active=false","DELETE FROM google_drive_connections",
    "TRUNCATE google_drive_imports","CREATE TABLE public.drive_forbidden(id int)","SET ROLE drive_helper_owner"])
def test_actual_runtime_login_forbidden_sql(runtime_url, statement):
    db=create_engine(runtime_url,hide_parameters=True)
    try:
        with db.connect() as c:
            assert c.scalar(text("SELECT current_user"))=="drive_runtime"
            with pytest.raises(DBAPIError) as failure:
                c.execute(text(statement))
            assert failure.value.orig.sqlstate=="42501"
    finally:
        db.dispose()


def test_runtime_persistence_positive_and_permissions_verifier(runtime_url, identities, engine):
    db=Database(runtime_url)
    user=DriveUser(str(identities["owner"]),identities["fingerprint"],identities["tenant"])
    try:
        repo=GoogleDriveRepository(db,user)
        from uuid import uuid4
        from app.interfaces.api.v1.schemas.google_drive_schema import GoogleDriveImportRequest
        payload=GoogleDriveImportRequest(operation_id=str(uuid4()),files=[{"file_id":"synthetic"}])
        record,_=repo.claim_import(payload.operation_id,"a"*64,payload,1)
        file=repo.list_import_files(record.import_id)[0]
        repo.journal_file(record,file.import_file_id,{"status":"FAILED","error_message":"synthetic"})
        assert repo.complete_operation(record).failed_files==1
        with engine.begin() as c:
            c.execute(text(Path("/drive-db/verify_role.sql").read_text()))
    finally:
        db.close()


def test_unexpected_grant_is_detected_and_rolled_back(engine):
    with engine.connect() as c:
        transaction=c.begin()
        try:
            c.execute(text("GRANT SELECT ON auth_user TO drive_runtime"))
            with pytest.raises(DBAPIError):
                c.execute(text(Path("/drive-db/verify_role.sql").read_text()))
        finally:
            transaction.rollback()
    with engine.begin() as c:
        c.execute(text(Path("/drive-db/verify_role.sql").read_text()))


@pytest.mark.parametrize("revoke", [False, True])
def test_enabled_callback_checks_current_identity_between_provider_calls(runtime_url, signing_keys, identities, engine, token, monkeypatch, revoke):
    from fastapi.testclient import TestClient
    from app.config.settings import Settings
    from app.main import create_app
    from app.infrastructure.google.drive_client import GoogleDriveClient
    called=[]

    def exchange(self, code, verifier):
        called.append("exchange")
        # A provider call must run without a lock on Auth; revocation can proceed here.
        if revoke:
            with engine.begin() as c:
                c.execute(text("SET LOCAL lock_timeout='1s'"))
                c.execute(text("UPDATE auth_user SET password='changed' WHERE id=:id"), {"id":identities["owner"]})
        return {"access_token":"synthetic-access", "refresh_token":"synthetic-refresh", "expires_in":300,"token_type":"Bearer"}

    def info(self, access):
        called.append("userinfo")
        return {"emailAddress":"synthetic@example.invalid","permissionId":"synthetic-subject"}

    monkeypatch.setattr(GoogleDriveClient,"exchange_code",exchange)
    monkeypatch.setattr(GoogleDriveClient,"get_userinfo",info)
    config=Settings(database_url=runtime_url,auth_jwt_public_key_path=signing_keys[1],google_drive_enabled=True,
                    google_oauth_client_id="synthetic",google_oauth_client_secret="synthetic-secret",google_token_encryption_key="a"*48)
    with TestClient(create_app(config)) as client:
        import base64
        import hashlib
        verifier="v"*43
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        attempt=client.post("/api/v1/google-drive/auth-url",json={"code_challenge":challenge},headers=token()).json()
        response=client.post("/api/v1/google-drive/oauth/callback",json={"code":"synthetic","state":attempt["state"],"code_verifier":verifier},headers=token())
        assert response.status_code == (401 if revoke else 200)
        assert called == (["exchange"] if revoke else ["exchange","userinfo"])
        assert "synthetic-access" not in response.text and "synthetic-refresh" not in response.text
    with engine.begin() as c:
        assert c.scalar(text("SELECT count(*) FROM google_drive_connections WHERE owner_user_id=:owner"),
                        {"owner":str(identities["owner"])}) == 1


def test_pool_timeout_rollback_and_statement_timeout(runtime_url):
    from sqlalchemy.exc import TimeoutError
    db=Database(runtime_url,1,1,1)
    try:
        with db.session() as first:
            assert first.scalar(text("SHOW statement_timeout"))=="1s"
            with pytest.raises(TimeoutError):
                with db.session() as second:
                    second.scalar(text("SELECT 1"))
        with pytest.raises(DBAPIError):
            with db.session() as c:
                c.execute(text("SELECT 1/0"))
        with db.session() as c:
            assert c.scalar(text("SELECT 1"))==1
    finally:
        db.close()


def test_key_loss_is_unready_but_live(client, signing_keys):
    public=signing_keys[1]
    saved=public.read_bytes()
    try:
        public.write_bytes(b"synthetic-invalid-public-key")
        assert client.get("/api/v1/health/db").json()=={"detail":"Drive dependencies are unavailable."}
        assert client.get("/api/v1/health/db").status_code==503
        assert client.get("/api/v1/health").status_code==200
    finally:
        public.write_bytes(saved)


def test_missing_column_is_unready_and_recovers(client, engine):
    with engine.begin() as c:
        c.execute(text("ALTER TABLE google_drive_imports RENAME COLUMN total_files TO synthetic_missing_total"))
    try:
        response=client.get("/api/v1/health/db")
        assert response.status_code==503
        assert response.json()=={"detail":"Drive dependencies are unavailable."}
    finally:
        with engine.begin() as c:
            c.execute(text("ALTER TABLE google_drive_imports RENAME COLUMN synthetic_missing_total TO total_files"))
    assert client.get("/api/v1/health/db").status_code==200


def test_repository_cannot_mutate_another_owners_import(runtime_url, identities, engine):
    from app.shared.errors import NotFoundError
    with engine.begin() as c:
        identifier=c.scalar(text("INSERT INTO google_drive_imports(owner_user_id) VALUES(:u) RETURNING import_id"),
                            {"u":str(identities["other"])})
        file_id=c.scalar(text("INSERT INTO google_drive_import_files(import_id,google_file_id,filename,mime_type) VALUES(:i,'synthetic','x.txt','text/plain') RETURNING import_file_id"),{"i":identifier})
    db=Database(runtime_url)
    repo=GoogleDriveRepository(db,DriveUser(str(identities["owner"]),identities["fingerprint"],identities["tenant"]))
    try:
        from types import SimpleNamespace
        from app.shared.errors import DriveConflictError
        foreign=SimpleNamespace(import_id=identifier,version=1,lease_token="synthetic")
        actions=[lambda:repo.get_connection(str(identities["other"])),lambda:repo.list_import_files(identifier),
                 lambda:repo.journal_file(foreign,file_id,{"status":"FAILED"}),
                 lambda:repo.complete_operation(foreign)]
        for action in actions:
            with pytest.raises((NotFoundError,DriveConflictError)):
                action()
    finally:
        db.close()


def test_global_connection_requires_permission_in_each_active_tenant(client, token, engine, identities):
    with engine.begin() as c:
        other_tenant=c.scalar(text("INSERT INTO tenants(name) VALUES('synthetic-other-tenant') RETURNING tenant_id"))
        c.execute(text("INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES(:t,:u,'TENANT_ADMIN')"),{"t":other_tenant,"u":str(identities["owner"])})
        c.execute(text("INSERT INTO google_drive_connections(owner_user_id,access_token_encrypted) VALUES(:u,'synthetic-ciphertext')"),{"u":str(identities["owner"])})
    try:
        assert client.get("/api/v1/google-drive/connection",headers=token()).json()["grant_status"] == "LEGACY"
        assert client.get("/api/v1/google-drive/connection",headers=token(active_tenant_id=other_tenant)).status_code==403
        with engine.begin() as c:
            group=c.scalar(text("INSERT INTO tenant_groups(tenant_id,name) VALUES(:t,'synthetic-drive') RETURNING group_id"),{"t":other_tenant})
            c.execute(text("INSERT INTO tenant_group_permissions(group_id,permission_code) VALUES(:g,'use_google_drive')"),{"g":group})
            c.execute(text("INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES(:t,:u,:g)"),{"t":other_tenant,"u":str(identities["owner"]),"g":group})
        assert client.get("/api/v1/google-drive/connection",headers=token(active_tenant_id=other_tenant)).json()["grant_status"] == "LEGACY"
        assert client.get("/api/v1/google-drive/connection",headers=token(user_id=identities["other"])).json()["connected"] is False
    finally:
        with engine.begin() as c:
            c.execute(text("DELETE FROM tenants WHERE tenant_id=:t"),{"t":other_tenant})
