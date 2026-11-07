"""Development-only HTTP contract probe; run inside auth-service, never print tokens."""
import json
import os
import secrets
import struct
import sys
import urllib.error
import urllib.request
from uuid import uuid4
import zlib

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


def photo(base, path, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=10) as response:
            assert response.headers.get_content_type() == "image/jpeg"
            assert response.headers["Cache-Control"] == "private, no-store"
            content = response.read(1048577)
            assert content.startswith(b"\xff\xd8") and len(content) <= 1048576
            return response.status, content
    except urllib.error.HTTPError as error:
        return error.code, b""


def upload(base, token, version, color):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress((b"\x00" + bytes(color) * 2) * 2)) + chunk(b"IEND", b""))
    boundary = uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="expected_version"\r\n\r\n{version}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.png"\r\n'
            'Content-Type: image/png\r\n\r\n').encode() + png + f"\r\n--{boundary}--\r\n".encode()
    with urllib.request.urlopen(urllib.request.Request(base + "/api/v1/profile/upload", data=body, headers={
        "Authorization": "Bearer " + token, "Content-Type": "multipart/form-data; boundary=" + boundary,
    }), timeout=10) as response:
        assert response.status == 200
        return json.load(response)


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
    marker = os.environ.get("PROFILE_PROBE_MARKER")
    if marker is not None and (len(marker) != 32 or any(c not in "0123456789abcdef" for c in marker)):
        raise RuntimeError("Invalid synthetic coordinator marker.")
    photos = []
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
            assert own["version"] == 0
            assert request(profile, "/api/v1/profile", token=pair["access"], body={"email": None}, method="PUT")[0] == 422
            assert request(profile, "/api/v1/profile", token=pair["access"], body={"expected_version": 1, "email": None}, method="PUT")[0] == 409
            assert request(profile, "/api/v1/profile", token=pair["access"])[1]["profile_id"] is None
            assert photo(profile, "/api/v1/profile/avatar")[0] == 401
            if marker:
                status, saved = request(profile, "/api/v1/profile", token=pair["access"], method="PUT", body={
                    "expected_version": 0, "additional_info": {"profile_probe": marker},
                })
                assert status == 200
                saved = upload(profile, pair["access"], saved["version"], [(255, 0, 0), (0, 255, 0), (0, 0, 255)][index])
                status, content = photo(profile, saved["profile_picture_url"], pair["access"])
                assert status == 200
                photos.append(content)
                old_path = saved["profile_picture_url"]
                status, saved = request(profile, "/api/v1/profile", token=pair["access"], method="PUT", body={
                    "expected_version": saved["version"], "email": None,
                })
                assert status == 200 and photo(profile, saved["profile_picture_url"], pair["access"])[1] == content
                assert photo(profile, old_path, pair["access"])[0] == 404
                if index == 0:
                    saved = upload(profile, pair["access"], saved["version"], (0, 255, 255))
                    status, cleared = request(profile, "/api/v1/profile/avatar", token=pair["access"], method="DELETE",
                                              body={"expected_version": saved["version"]})
                    assert status == 200 and cleared["profile_picture_url"] is None
                    assert photo(profile, "/api/v1/profile/avatar", pair["access"])[0] == 404
            status, renewed = request(auth, "/api/users/token/refresh/", body={"refresh": pair["refresh"]})
            assert status == 200, "Synthetic token refresh failed"
            assert request(profile, "/api/v1/profile", token=renewed["access"])[0] == 200
            assert request(profile, "/api/v1/profile", token=pair["refresh"])[0] == 401
            for path in ("/api/v1/profiles", "/api/v1/profiles/" + str(users[0].pk)):
                assert request(profile, path, token=pair["access"])[0] == 404
                assert request(profile, path, token=pair["access"], body={}, method="PUT")[0] == 404

        new_password = secrets.token_urlsafe(32)
        if marker:
            assert len(set(photos)) == 3
        assert request(auth, "/api/users/change-password/", token=pairs[0]["access"], body={
            "old_password": passwords[0], "new_password": new_password,
        })[0] == 200
        assert request(profile, "/api/v1/profile", token=pairs[0]["access"])[0] == 401
        assert request(auth, "/api/users/token/refresh/", body={"refresh": pairs[0]["refresh"]})[0] == 401
        status, pair = request(auth, "/api/users/login/", body={"username": users[0].username, "password": new_password})
        assert status == 200 and request(profile, "/api/v1/profile", token=pair["access"])[0] == 200

        User.objects.filter(pk=users[1].pk).update(is_active=False)
        assert request(profile, "/api/v1/profile", token=pairs[1]["access"])[0] == 401
        assert photo(profile, "/api/v1/profile/avatar", pairs[1]["access"])[0] == 401
        User.objects.filter(pk=users[2].pk).delete()
        assert request(profile, "/api/v1/profile", token=pairs[2]["access"])[0] == 401
        assert photo(profile, "/api/v1/profile/avatar", pairs[2]["access"])[0] == 401
        print("Profile HTTP: login/refresh, own-only access, version preconditions and revocation OK")
    finally:
        if tenant:
            TenantMembership.objects.filter(tenant=tenant).delete()
            Tenant.objects.filter(pk=tenant.pk).delete()
            assert not Tenant.objects.filter(pk=tenant.pk).exists()
        User.objects.filter(pk__in=identifiers).delete()
        LoginAttemptBudget.objects.filter(key__in=account_keys).delete()
        assert not User.objects.filter(pk__in=identifiers).exists()
        assert not LoginAttemptBudget.objects.filter(key__in=account_keys).exists()
        print("Profile HTTP: identities, tenant and account budgets cleaned; " +
              ("tagged profiles require coordinator cleanup" if marker else "no profiles/files written"))


if __name__ == "__main__":
    main()
