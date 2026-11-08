"""Synthetic development probe; execute inside auth-service, never print JWTs."""
import json
import os
import secrets
import sys
import urllib.error
import urllib.request

import django


def request(base, path, *, body=None, token=None, method=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    query = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(query, timeout=15) as response:
            if response.headers.get_content_type() == "application/pdf":
                content = response.read(1024 * 1024 + 1)
                assert len(content) <= 1024 * 1024 and content.startswith(b"%PDF-")
                return response.status, content
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    marker = os.environ.get("EXPORT_PROBE_MARKER", "")
    if os.environ.get("AUTH_ENV") != "development" or len(marker) != 32 or any(c not in "0123456789abcdef" for c in marker):
        raise RuntimeError("Explicit synthetic development marker is required.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    sys.path.insert(0, "/app")
    django.setup()
    from django.contrib.auth.models import User
    from django.utils.crypto import salted_hmac
    from users.models import LoginAttemptBudget, Tenant, TenantMembership

    auth, export, conversation = "http://127.0.0.1:8001", "http://document-export-service:8000", "http://conversation-service:8000"
    users, passwords, pairs, saved, references, budgets = [], [], [], [], [], []
    tenant = None
    title = "EXPORT003-" + marker
    try:
        for index in range(3):
            password = secrets.token_urlsafe(32)
            user = User.objects.create_user(username="export003-" + marker + "-" + str(index), password=password,
                                            is_superuser=index == 2, is_staff=index == 2)
            users.append(user)
            passwords.append(password)
            budgets.append(salted_hmac("auth-login-budget", "account:" + user.username, algorithm="sha256").hexdigest())
        tenant = Tenant.objects.create(name=title)
        TenantMembership.objects.create(tenant=tenant, user_id=str(users[1].pk), role="TENANT_ADMIN")
        for index, user in enumerate(users):
            status, pair = request(auth, "/api/users/login/", body={"username": user.username, "password": passwords[index]})
            assert status == 200
            pairs.append(pair)
            if index == 1:
                assert "TENANT_ADMIN" in pair["user"]["roles"]
            if index == 2:
                assert pair["user"]["is_superadmin"] is True
            assert request(export, "/api/v1/exports", token=pair["access"]) == (200, {"items": [], "next_cursor": None})
            assert request(export, "/api/v1/exports", token=pair["refresh"])[0] == 401
            status, renewed = request(auth, "/api/users/token/refresh/", body={"refresh": pair["refresh"]})
            assert status == 200 and request(export, "/api/v1/exports", token=renewed["access"])[0] == 200
            status, chat = request(conversation, "/api/v1/conversations", token=pair["access"], body={"title": title})
            assert status == 200
            chat_id = chat["conversation_id"]
            status, message = request(conversation, f"/api/v1/conversations/{chat_id}/messages", token=pair["access"],
                                      body={"role": "assistant", "content": "Synthetic reference", "sources": [], "metadata": {}})
            assert status == 200
            refs = {"conversation_id": chat_id, "message_id": message["message_id"]}
            references.append(refs)
            status, created = request(export, "/api/v1/exports/chat-message/pdf", token=pair["access"], body={
                **refs, "title": title, "answer": "Synthetic client snapshot", "metadata": {"export_probe": marker},
            })
            assert status == 200 and created["conversation_id"] == chat_id
            assert "storage_path" not in created and "owner_user_id" not in created
            saved.append(created)
            assert request(export, created["download_url"], token=pair["access"])[0] == 200
        for index, pair in enumerate(pairs):
            own = request(export, "/api/v1/exports", token=pair["access"])
            assert own[0] == 200 and [row["export_id"] for row in own[1]["items"]] == [saved[index]["export_id"]]
            other = (index + 1) % 3
            for suffix in ["", "/status", "/download"]:
                assert request(export, "/api/v1/exports/" + saved[other]["export_id"] + suffix, token=pair["access"])[0] == 404
            assert request(export, "/api/v1/exports/chat-message/pdf", token=pair["access"], body={
                **references[other], "answer": "Rejected cross-owner snapshot", "title": title,
                "metadata": {"export_probe": marker},
            })[0] == 404
        new_password = secrets.token_urlsafe(32)
        assert request(auth, "/api/users/change-password/", token=pairs[0]["access"], body={
            "old_password": passwords[0], "new_password": new_password,
        })[0] == 200
        assert request(export, "/api/v1/exports", token=pairs[0]["access"])[0] == 401
        assert request(auth, "/api/users/token/refresh/", body={"refresh": pairs[0]["refresh"]})[0] == 401
        status, renewed = request(auth, "/api/users/login/", body={"username": users[0].username, "password": new_password})
        assert status == 200 and request(export, saved[0]["download_url"], token=renewed["access"])[0] == 200
        User.objects.filter(pk=users[1].pk).update(is_active=False)
        User.objects.filter(pk=users[2].pk).delete()
        for index in [1, 2]:
            for path in ["/api/v1/exports", saved[index]["download_url"]]:
                assert request(export, path, token=pairs[index]["access"])[0] == 401
            assert request(export, "/api/v1/exports/chat-message/pdf", token=pairs[index]["access"], body={"answer": "Rejected"})[0] == 401
        print("Export HTTP: real login/refresh, three roles, owner-only PDFs/references and revocation OK")
    finally:
        identifiers = [user.pk for user in users]
        if tenant:
            TenantMembership.objects.filter(tenant=tenant).delete()
            Tenant.objects.filter(pk=tenant.pk).delete()
        User.objects.filter(pk__in=identifiers).delete()
        LoginAttemptBudget.objects.filter(key__in=budgets).delete()
        assert not User.objects.filter(pk__in=identifiers).exists()
        assert not LoginAttemptBudget.objects.filter(key__in=budgets).exists()
        print("Export HTTP: identities and account budgets cleaned; coordinator must remove tagged synthetic PDFs/references")


if __name__ == "__main__":
    main()
