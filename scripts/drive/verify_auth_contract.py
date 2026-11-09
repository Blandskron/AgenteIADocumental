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
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    marker = os.environ.get("DRIVE_PROBE_MARKER", "")
    if os.environ.get("AUTH_ENV") != "development" or len(marker) != 32 or any(c not in "0123456789abcdef" for c in marker):
        raise RuntimeError("Explicit synthetic development marker is required.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    sys.path.insert(0, "/app")
    django.setup()
    from django.contrib.auth.models import User
    from django.utils.crypto import salted_hmac
    from users.models import LoginAttemptBudget, Tenant, TenantMembership, TenantGroup, TenantUserGroup, TenantGroupPermission

    auth, drive = "http://127.0.0.1:8001", "http://google-drive-import-service:8000"
    users, passwords, pairs, budgets = [], [], [], []
    tenant = None
    try:
        tenant = Tenant.objects.create(name="DRIVE002-" + marker)
        group = TenantGroup.objects.create(tenant=tenant, name="DRIVE002-" + marker)
        TenantGroupPermission.objects.create(group=group, permission_code="use_google_drive")
        for index, role in enumerate(("USER", "TENANT_ADMIN", "SUPERADMIN")):
            password = secrets.token_urlsafe(32)
            user = User.objects.create_user(username="drive002-" + marker + "-" + str(index), password=password,
                                            is_superuser=index == 2, is_staff=index == 2)
            users.append(user)
            budgets.append(salted_hmac("auth-login-budget", "account:" + user.username, algorithm="sha256").hexdigest())
            passwords.append(password)
            if index < 2:
                TenantMembership.objects.create(tenant=tenant, user_id=str(user.pk), role=role)
                TenantUserGroup.objects.create(tenant=tenant, user_id=str(user.pk), group=group)
            status, pair = request(auth, "/api/users/login/", body={"username":user.username,"password":password})
            assert status == 200
            pairs.append(pair)
            assert request(drive, "/api/v1/google-drive/imports", token=pair["access"]) == (200, {"items": [], "next_cursor": None})
            assert request(drive, "/api/v1/google-drive/imports", token=pair["refresh"])[0] == 401
            assert request(drive, "/api/v1/google-drive/auth-url", token=pair["access"])[0] == 503
            status, renewed = request(auth, "/api/users/token/refresh/", body={"refresh":pair["refresh"]})
            assert status == 200
            assert request(drive, "/api/v1/google-drive/connection", token=renewed["access"])[0] == 200

        # Current database permission wins over unchanged signed claims.
        TenantGroupPermission.objects.filter(group=group).delete()
        for pair in pairs[:2]:
            assert request(drive, "/api/v1/google-drive/imports", token=pair["access"])[0] == 403
        assert request(drive, "/api/v1/google-drive/imports", token=pairs[2]["access"])[0] == 200
        TenantGroupPermission.objects.create(group=group, permission_code="use_google_drive")

        new_password=secrets.token_urlsafe(32)
        assert request(auth, "/api/users/change-password/", token=pairs[0]["access"],
                       body={"old_password":passwords[0],"new_password":new_password})[0] == 200
        assert request(drive, "/api/v1/google-drive/imports", token=pairs[0]["access"])[0] == 401
        User.objects.filter(pk=users[1].pk).update(is_active=False)
        assert request(drive, "/api/v1/google-drive/imports", token=pairs[1]["access"])[0] == 401
        users[2].delete()
        assert request(drive, "/api/v1/google-drive/imports", token=pairs[2]["access"])[0] == 401
        print("Drive HTTP: real login/refresh, three roles, current permission, password/inactive/deleted revocation OK; no Google calls")
    finally:
        # Scope cleanup to unique usernames, tenant and their login budgets, never application documents.
        User.objects.filter(username__startswith="drive002-" + marker + "-").delete()
        if tenant:
            tenant.delete()
        LoginAttemptBudget.objects.filter(key__in=budgets).delete()
        assert not User.objects.filter(username__startswith="drive002-" + marker + "-").exists()
        assert not LoginAttemptBudget.objects.filter(key__in=budgets).exists()
        print("Drive HTTP: tagged synthetic identities/tenant cleaned")


if __name__ == "__main__":
    main()
