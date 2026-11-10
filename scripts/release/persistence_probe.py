"""Synthetic lifecycle probe; state stays private inside one disposable test container."""
import json
import os
from pathlib import Path
import secrets
import sys

import httpx
import psycopg


def run(phase):
    if os.environ.get("RELEASE_VERIFICATION") != "bd-final-check":
        raise RuntimeError("Dedicated synthetic verification required")
    state_file = Path("/tmp/closure-persistence.json")
    user = os.environ["INITIAL_ADMIN_USERNAME"]
    initial_password = os.environ["INITIAL_ADMIN_PASSWORD"]
    with psycopg.connect(host="postgres", dbname="documents_db", user="postgres",
                         password=os.environ["PGPASSWORD"], autocommit=True) as db, httpx.Client(timeout=300, trust_env=False) as client:
        def login(password, expected=200):
            response = client.post("http://auth-service:8001/api/users/login/", json={"username": user, "password": password})
            if response.status_code != expected:
                raise AssertionError("Synthetic bootstrap login failed")
            return response.json().get("access")

        def request(service, method, route, token, **kwargs):
            response = client.request(method, "http://" + service + route,
                                      headers={"Authorization": "Bearer " + token}, **kwargs)
            if response.status_code != 200:
                raise AssertionError(f"Synthetic persistence operation failed: {service} {route} ({response.status_code})")
            return response

        if phase == "prepare":
            if user != "synthetic-release-admin":
                raise RuntimeError("Refusing a non-synthetic administrator")
            token = login(initial_password)
            row = db.execute("SELECT id,password FROM auth_user WHERE username=%s AND is_superuser", (user,)).fetchone()
            changed_password = secrets.token_urlsafe(32)
            # Persist recovery information before any mutation.
            state = {"user_id": row[0], "original_hash": row[1], "password": changed_password, "document_id": None}
            with state_file.open("x", encoding="utf8") as handle:
                state_file.chmod(0o600)
                json.dump(state, handle)
            try:
                uploaded = request("rag-document-embedding-service:8000", "POST", "/api/v1/documents/upload", token,
                                   files={"file": ("synthetic-persistence.txt", b"Synthetic persistence sentinel 97 days.", "text/plain")},
                                   data={"process": "true"}).json()
                state["document_id"] = uploaded["document_id"]
                state_file.write_text(json.dumps(state), encoding="utf8")
                request("auth-service:8001", "POST", "/api/users/change-password/", token,
                        json={"old_password": initial_password, "new_password": changed_password})
                stale = client.get("http://document-search-service:8000/api/v1/documents/search",
                                   headers={"Authorization": "Bearer " + token})
                assert stale.status_code == 401
                state["changed_hash"] = db.execute("SELECT password FROM auth_user WHERE id=%s", (row[0],)).fetchone()[0]
                state_file.write_text(json.dumps(state), encoding="utf8")
            except Exception:
                # Keep recovery state; orchestrator always invokes cleanup in finally.
                raise
        else:
            state = json.loads(state_file.read_text(encoding="utf8"))
            if phase == "verify":
                row = db.execute("SELECT id,password FROM auth_user WHERE username=%s", (user,)).fetchone()
                assert row == (state["user_id"], state["changed_hash"])
                assert db.execute("SELECT count(*) FROM auth_user WHERE is_superuser").fetchone()[0] == 1
                login(initial_password, expected=400)
                token = login(state["password"])
                content = request("document-access-service:8000", "GET", f"/api/v1/documents/{state['document_id']}/download", token)
                assert b"Synthetic persistence sentinel" in content.content
                assert db.execute("SELECT count(*) FROM documents WHERE document_id=%s", (state["document_id"],)).fetchone()[0] == 1
            elif phase == "cleanup":
                if state["document_id"]:
                    # Own synthetic fixture only; no bulk table or volume deletion.
                    db.execute("UPDATE auth_user SET password=%s WHERE id=%s AND username=%s",
                               (state["original_hash"], state["user_id"], user))
                    token = login(initial_password)
                    request("document-access-service:8000", "DELETE", f"/api/v1/documents/{state['document_id']}", token)
                    db.execute("DELETE FROM document_deletions WHERE document_id=%s AND completed_at IS NOT NULL", (state["document_id"],))
                    db.execute("DELETE FROM audit_logs WHERE resource_type='DOCUMENT' AND resource_id=%s", (state["document_id"],))
                db.execute("UPDATE auth_user SET password=%s WHERE id=%s AND username=%s",
                           (state["original_hash"], state["user_id"], user))
                state_file.unlink()
            else:
                raise ValueError("Unknown phase")
    print(json.dumps({"probe": "bootstrap-persistence", "phase": phase, "result": "passed"}))


if __name__ == "__main__":
    run(sys.argv[1])
