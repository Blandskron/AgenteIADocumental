from os import environ
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, text

from app.config.settings import get_settings
from app.infrastructure.database.models import AuditLogModel, AuthUserModel, DocumentModel, NotificationModel, TenantModel
from app.main import app


@pytest.fixture(scope="module")
def assignment_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def workflow(tmp_path, monkeypatch, assignment_key):
    engine = create_engine(environ["ACCESS_TEST_DATABASE_URL"])
    runtime_engine = create_engine(get_settings().database_url)
    tenant, foreign_tenant = uuid4().hex, uuid4().hex
    users, documents = {}, {name: uuid4().hex for name in ("owned", "private", "foreign")}
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Synthetic workflow')"), [
                {"id": tenant}, {"id": foreign_tenant},
            ])
            for name in ("manager", "leader", "recipient", "other", "outsider", "super"):
                users[name] = str(connection.scalar(text("""
                    INSERT INTO auth_user
                        (password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined)
                    VALUES ('!', :superuser, :username, '', '', '', false, true, now()) RETURNING id
                """), {"superuser": name == "super", "username": f"synthetic-{uuid4().hex}"}))
                if name != "super":
                    connection.execute(text("""
                        INSERT INTO tenant_memberships (tenant_id, user_id, role, status)
                        VALUES (:tenant, :user, :role, 'ACTIVE')
                    """), {
                        "tenant": foreign_tenant if name == "outsider" else tenant,
                        "user": users[name],
                        "role": {"manager": "TENANT_ADMIN", "outsider": "TENANT_ADMIN", "leader": "LEADER"}.get(name, "USER"),
                    })
            for name, document_id in documents.items():
                connection.execute(text("""
                    INSERT INTO documents (document_id, tenant_id, owner_user_id, filename, storage_path, mime_type)
                    VALUES (:id, :tenant, :owner, 'synthetic.txt', 'synthetic-workflow.txt', 'text/plain')
                """), {
                    "id": document_id, "tenant": foreign_tenant if name == "foreign" else tenant,
                    "owner": users[{"owned": "leader", "private": "manager", "foreign": "outsider"}[name]],
                })

        public_key = tmp_path / "public.pem"
        public_key.write_bytes(assignment_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        settings = get_settings().model_copy(update={"auth_jwt_public_key_path": str(public_key)})
        monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: settings)

        async def paused_cleanup(database, path_resolver, stop):
            await stop.wait()

        monkeypatch.setattr("app.main.deletion_cleanup_loop", paused_cleanup)
        with TestClient(app, raise_server_exceptions=False) as client:
            def request(method, path, actor="manager", payload=None, **claims):
                token = jwt.encode({
                    "user_id": int(users[actor]), "token_type": "access", "exp": 4102444800, **claims,
                }, assignment_key, algorithm="RS256")
                return client.request(method, f"/api/v1/documents/{path}", json=payload, headers={"Authorization": f"Bearer {token}"})

            def post(path, actor="manager", payload=None, **claims):
                return request("POST", path, actor, payload, **claims)

            def get(path, actor="manager"):
                return request("GET", path, actor)

            def assign(actor="manager", recipient="recipient", document="owned", **fields):
                return post(f"{documents[document]}/assignments", actor, {
                    "assigned_to_user_id": users.get(recipient, recipient), **fields,
                })

            yield SimpleNamespace(
                engine=engine, runtime_engine=runtime_engine, client=client, users=users, documents=documents, tenant=tenant, foreign_tenant=foreign_tenant,
                post=post, get=get, assign=assign,
            )
    finally:
        with engine.begin() as connection:
            connection.execute(delete(DocumentModel).where(DocumentModel.document_id.in_(documents.values())))
            connection.execute(delete(NotificationModel).where(NotificationModel.recipient_user_id.in_(users.values())))
            connection.execute(delete(AuditLogModel).where(AuditLogModel.actor_user_id.in_(users.values())))
            connection.execute(delete(TenantModel).where(TenantModel.tenant_id.in_([tenant, foreign_tenant])))
            connection.execute(delete(AuthUserModel).where(AuthUserModel.id.in_([int(value) for value in users.values()])))
        engine.dispose()
        runtime_engine.dispose()
