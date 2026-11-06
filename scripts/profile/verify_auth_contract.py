"""Development-only HTTP contract probe; run inside auth-service, never print tokens."""
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from uuid import uuid4

import django


def request(base, path, *, body=None, token=None, method=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    query = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(query, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    if os.environ.get("AUTH_ENV") != "development":
        raise RuntimeError("This synthetic contract probe requires AUTH_ENV=development.")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    sys.path.insert(0, "/app")
    django.setup()
    from django.contrib.auth.models import User
    from django.utils.crypto import salted_hmac
    from users.models import LoginAttemptBudget, Tenant, TenantMembership

    auth, profile = "http://127.0.0.1:8001", "http://profile-service:8000"
    users, passwords, pairs = [], [], []
    tenant = None
    account_keys = []
    identifiers = []
    try:
        for index in range(3):
            password = secrets.token_urlsafe(32)
            username = "profile003-http-" + uuid4().hex
            user = User.objects.create_user(username=username, password=password,
                                            is_superuser=index == 2, is_staff=index == 2)
            users.append(user)
            identifiers.append(user.pk)
            passwords.append(password)
            account_keys.append(salted_hmac("auth-login-budget", "account:" + username, algorithm="sha256").hexdigest())
        tenant = Tenant.objects.create(name="PROFILE-003 synthetic tenant")
        TenantMembership.objects.create(tenant=tenant, user_id=str(users[1].pk), role="TENANT_ADMIN")

        for index, user in enumerate(users):
            status, pair = request(auth, "/api/users/login/", body={"username": user.username, "password": passwords[index]})
            assert status == 200, "Synthetic login failed"
            pairs.append(pair)
            if index == 1:
                assert "TENANT_ADMIN" in pair["user"]["roles"]
            if index == 2:
                assert pair["user"]["is_superadmin"] is True
            status, own = request(profile, "/api/v1/profile", token=pair["access"])
            assert status == 200 and own["user_id"] == str(user.pk) and own["profile_id"] is None
            status, renewed = request(auth, "/api/users/token/refresh/", body={"refresh": pair["refresh"]})
            assert status == 200, "Synthetic token refresh failed"
            assert request(profile, "/api/v1/profile", token=renewed["access"])[0] == 200
            assert request(profile, "/api/v1/profile", token=pair["refresh"])[0] == 401
            for path in ("/api/v1/profiles", "/api/v1/profiles/" + str(users[0].pk)):
                assert request(profile, path, token=pair["access"])[0] == 404
                assert request(profile, path, token=pair["access"], body={}, method="PUT")[0] == 404

        new_password = secrets.token_urlsafe(32)
        assert request(auth, "/api/users/change-password/", token=pairs[0]["access"], body={
            "old_password": passwords[0], "new_password": new_password,
        })[0] == 200
        assert request(profile, "/api/v1/profile", token=pairs[0]["access"])[0] == 401
        assert request(auth, "/api/users/token/refresh/", body={"refresh": pairs[0]["refresh"]})[0] == 401
        status, pair = request(auth, "/api/users/login/", body={"username": users[0].username, "password": new_password})
        assert status == 200 and request(profile, "/api/v1/profile", token=pair["access"])[0] == 200

        User.objects.filter(pk=users[1].pk).update(is_active=False)
        assert request(profile, "/api/v1/profile", token=pairs[1]["access"])[0] == 401
        User.objects.filter(pk=users[2].pk).delete()
        assert request(profile, "/api/v1/profile", token=pairs[2]["access"])[0] == 401
        print("PROFILE-003 HTTP: login/refresh, own-only profiles, password revocation, inactive/deleted users OK")
    finally:
        if tenant:
            TenantMembership.objects.filter(tenant=tenant).delete()
            Tenant.objects.filter(pk=tenant.pk).delete()
            assert not Tenant.objects.filter(pk=tenant.pk).exists()
        User.objects.filter(pk__in=identifiers).delete()
        LoginAttemptBudget.objects.filter(key__in=account_keys).delete()
        assert not User.objects.filter(pk__in=identifiers).exists()
        assert not LoginAttemptBudget.objects.filter(key__in=account_keys).exists()
        print("PROFILE-003 HTTP: synthetic identities, tenant and account budgets cleaned; no profile/files written")


if __name__ == "__main__":
    main()
