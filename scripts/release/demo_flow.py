"""End-to-end synthetic HTTP flow. Refuses a DB outside the dedicated Compose project."""

import base64
import hashlib
import io
import json
import os
import secrets
import time
from uuid import uuid4

import httpx
import psycopg
from pypdf import PdfReader


class SimulatedLostUploadResponse(Exception):
    """Verification-only fault after a real upload committed, before its ID is received."""


def run():
    if os.environ.get("RELEASE_VERIFICATION") != "bd-final-check":
        raise RuntimeError("Dedicated verification environment required")
    connection = psycopg.connect(
        host="postgres",
        dbname="documents_db",
        user="postgres",
        password=os.environ["PGPASSWORD"],
        autocommit=True,
    )
    marker = "synthetic-release-" + uuid4().hex
    filename = "blandskron-demo-" + marker + ".txt"
    password = secrets.token_urlsafe(24)
    salt = secrets.token_hex(12)
    encoded = base64.b64encode(
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 1200000)
    ).decode()
    encoded = f"pbkdf2_sha256$1200000${salt}${encoded}"
    users, documents, exports = [], [], []
    checks = []
    started = time.monotonic()
    client = httpx.Client(timeout=300, trust_env=False)

    def request(service, method, route, token=None, expected=200, **kwargs):
        print(f"Synthetic check: {service} {method} {route}", flush=True)
        headers = {"Authorization": "Bearer " + token} if token else {}
        response = client.request(
            method, "http://" + service + route, headers=headers, **kwargs
        )
        if response.status_code != expected:
            raise AssertionError(
                f"Synthetic {service} {route} expected {expected}, received {response.status_code}"
            )
        if os.environ.get("DEMO_LOST_UPLOAD_RESPONSE") == "1" and route == "/api/v1/documents/upload":
            raise SimulatedLostUploadResponse()
        return response

    try:
        with connection.transaction():
            tenant = connection.execute(
                "INSERT INTO tenants(name) VALUES(%s) RETURNING tenant_id", (marker,)
            ).fetchone()[0]
            group = connection.execute(
                "INSERT INTO tenant_groups(tenant_id,name) VALUES(%s,%s) RETURNING group_id",
                (tenant, marker),
            ).fetchone()[0]
            for permission in (
                "view_documents",
                "upload_documents",
                "download_documents",
                "use_chat",
            ):
                connection.execute(
                    "INSERT INTO tenant_group_permissions(group_id,permission_code) VALUES(%s,%s)",
                    (group, permission),
                )
            for suffix in ("owner", "observer"):
                uid = connection.execute(
                    "INSERT INTO auth_user(username,password,first_name,last_name,email,is_superuser,is_staff,is_active,date_joined) VALUES(%s,%s,'','','',false,false,true,now()) RETURNING id",
                    (marker + suffix, encoded),
                ).fetchone()[0]
                users.append(uid)
                connection.execute(
                    "INSERT INTO tenant_memberships(tenant_id,user_id,role) VALUES(%s,%s,'USER')",
                    (tenant, str(uid)),
                )
                connection.execute(
                    "INSERT INTO tenant_user_groups(tenant_id,user_id,group_id) VALUES(%s,%s,%s)",
                    (tenant, str(uid), group),
                )
        tokens = [
            request(
                "auth-service:8001",
                "POST",
                "/api/users/login/",
                json={"username": marker + suffix, "password": password},
            ).json()["access"]
            for suffix in ("owner", "observer")
        ]
        checks.append(
            "real Auth login: two users with current tenant/group permissions"
        )
        upload = request(
            "rag-document-embedding-service:8000",
            "POST",
            "/api/v1/documents/upload",
            tokens[0],
            files={
                "file": (
                    filename,
                    "El contrato sintético de demostración tiene una duración de 97 días.".encode(),
                    "text/plain",
                )
            },
            data={"process": "true"},
        ).json()
        documents.append(upload["document_id"])
        assert upload["status"] == "PROCESSED"
        checks.append(
            "upload, extraction, real local e5-small embeddings and PostgreSQL pgvector"
        )
        request(
            "rag-document-embedding-service:8000",
            "POST",
            f"/api/v1/documents/{documents[0]}/reindex",
            tokens[0],
        )
        for index, token in enumerate(tokens):
            found = request(
                "document-search-service:8000",
                "GET",
                "/api/v1/documents/search",
                token,
                params={"q": filename},
            ).json()
            assert (documents[0] in [row["document_id"] for row in found["items"]]) == (
                index == 0
            )
            answer = request(
                "rag-document-chat-service:8000",
                "POST",
                "/api/v1/chat/ask",
                token,
                json={
                    "question": "¿Cuántos días dura el contrato?",
                    "document_ids": documents,
                },
            ).json()
            assert (
                documents[0] in [source["document_id"] for source in answer["sources"]]
            ) == (index == 0)
            if index == 0:
                assert "97" in answer["answer"]
                owner_answer = answer
        checks.append(
            "owner-only search and RAG context; Groq HTTP transport simulated explicitly"
        )
        exported = request(
            "document-export-service:8000",
            "POST",
            "/api/v1/exports/chat-message/pdf",
            tokens[0],
            json={
                "title": "Demo sintética Blandskron",
                "question": "¿Cuántos días dura el contrato?",
                "answer": owner_answer["answer"],
                "sources": owner_answer["sources"],
            },
        ).json()
        exports.append(exported["export_id"])
        pdf = request(
            "document-export-service:8000",
            "GET",
            f"/api/v1/exports/{exports[0]}/download",
            tokens[0],
        )
        assert "application/pdf" in pdf.headers["content-type"]
        assert "97" in " ".join(
            page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages
        )
        request(
            "document-export-service:8000",
            "GET",
            f"/api/v1/exports/{exports[0]}/download",
            tokens[1],
            expected=404,
        )
        checks.append(
            "real Unicode PDF render/extraction/download; cross-owner download rejected"
        )
        connection.execute("DELETE FROM tenant_group_permissions WHERE group_id=%s AND permission_code='use_chat'", (group,))
        request("rag-document-chat-service:8000", "POST", "/api/v1/chat/ask", tokens[0], expected=403,
                json={"question": "Synthetic permission removed", "document_ids": documents})
        connection.execute("INSERT INTO tenant_group_permissions(group_id,permission_code) VALUES(%s,'use_chat')", (group,))
        checks.append("removing a group permission immediately denies chat with the previously issued JWT")
        connection.execute(
            "UPDATE auth_user SET is_active=false WHERE id=%s", (users[0],)
        )
        request("auth-service:8001", "GET", "/api/users/me/", tokens[0], expected=401)
        for service, route in (
            ("rag-document-chat-service:8000", "/api/v1/chat/ask"),
            ("rag-document-embedding-service:8000", f"/api/v1/documents/{documents[0]}/status"),
            ("document-search-service:8000", "/api/v1/documents/search"),
            ("document-access-service:8000", f"/api/v1/documents/{documents[0]}/content"),
            ("document-library-service:8000", "/api/v1/folders"),
            ("document-transfer-service:8000", "/api/v1/transfers"),
            ("conversation-service:8000", "/api/v1/conversations"),
        ):
            kwargs = {"json": {"question": "Synthetic", "document_ids": documents}} if service.startswith("rag-document-chat") else {}
            request(service, "POST" if kwargs else "GET", route, tokens[0], expected=401, **kwargs)
        request(
            "document-export-service:8000",
            "GET",
            f"/api/v1/exports/{exports[0]}/download",
            tokens[0],
            expected=401,
        )
        checks.append(
            "disabled account rejected by all seven legacy services and PDF with an existing JWT"
        )
        print(
            json.dumps(
                {
                    "card": "DEMO-001",
                    "mode": "synthetic Groq transport; real embedding model and service HTTP/SQL",
                    "checks": checks,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                },
                ensure_ascii=False,
            )
        )
    finally:
        # Cleanup belongs only to these random synthetic identities, never an entire volume/table.
        with connection.transaction():
            if exports:
                connection.execute(
                    "DELETE FROM document_exports WHERE export_id=ANY(%s)", (exports,)
                )
            if documents or users:
                connection.execute(
                    "DELETE FROM documents WHERE document_id=ANY(%s) OR (owner_user_id=ANY(%s) AND filename=%s)",
                    (documents, [str(uid) for uid in users], filename),
                )
            if users:
                connection.execute(
                    "DELETE FROM token_blacklist_outstandingtoken WHERE user_id=ANY(%s)",
                    (users,),
                )
                connection.execute("DELETE FROM tenants WHERE name=%s", (marker,))
                connection.execute("DELETE FROM auth_user WHERE id=ANY(%s)", (users,))
        client.close()
        connection.close()


if __name__ == "__main__":
    try:
        run()
    except SimulatedLostUploadResponse:
        print("Synthetic lost upload response injected; cleanup completed.")
    else:
        if os.environ.get("DEMO_LOST_UPLOAD_RESPONSE") == "1":
            raise AssertionError("The expected synthetic fault was not reached.")
