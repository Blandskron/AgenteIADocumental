import json
import os
from time import time
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import User
from django.db import connection
from rest_framework.test import APITestCase

from users.models import (
    AuditLog,
    Tenant,
    TenantArea,
    TenantGroup,
    TenantGroupPermission,
    TenantIntegration,
    TenantMembership,
    TenantUserGroup,
)


def _make_rsa_jwk_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk_dict = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk_dict["kid"] = "google-test-kid"
    return private_key, {"keys": [jwk_dict]}


class RegistrationAndGoogleOidcTests(APITestCase):
    unmanaged_models = (
        Tenant,
        TenantArea,
        TenantMembership,
        TenantGroup,
        TenantGroupPermission,
        TenantUserGroup,
        TenantIntegration,
        AuditLog,
    )

    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as schema:
            for model in cls.unmanaged_models:
                schema.create_model(model)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as schema:
            for model in reversed(cls.unmanaged_models):
                schema.delete_model(model)

    def test_first_registration_bootstraps_admin_and_subsequent_users_are_non_admin(self):
        status_before = self.client.get("/api/users/setup-status/")
        self.assertEqual(status_before.status_code, 200)
        self.assertTrue(status_before.data["needs_setup"])
        self.assertFalse(status_before.data["google_login_enabled"])

        # First registration creates superuser + default workspace + TENANT_ADMIN
        first = self.client.post(
            "/api/users/register/",
            {
                "email": "founder@synthetic.local",
                "password": "StrongFounderPass!234",
                "workspace_name": "Blandskron Demo",
            },
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.data["is_initial_admin"])
        self.assertTrue(first.data["user"]["is_superuser"])
        self.assertEqual(first.data["user"]["active_role"], "TENANT_ADMIN")
        self.assertIn("access", first.data)
        decoded_first = jwt.decode(first.data["access"], options={"verify_signature": False})
        self.assertEqual(decoded_first["active_role"], "TENANT_ADMIN")
        self.assertEqual(decoded_first["active_tenant_id"], first.data["user"]["active_tenant_id"])
        self.assertIn("roles", decoded_first)
        self.assertIn("tenant_memberships", decoded_first)

        status_after = self.client.get("/api/users/setup-status/")
        self.assertFalse(status_after.data["needs_setup"])

        # Subsequent registration MUST NOT receive admin privileges
        second = self.client.post(
            "/api/users/register/",
            {
                "email": "member@synthetic.local",
                "password": "StrongMemberPass!234",
            },
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertFalse(second.data["is_initial_admin"])
        self.assertFalse(second.data["user"]["is_superuser"])
        self.assertFalse(second.data["user"]["is_staff"])

        # Duplicate email is rejected with 409
        dup = self.client.post(
            "/api/users/register/",
            {"email": "FOUNDER@synthetic.local", "password": "StrongOtherPass!234"},
            format="json",
        )
        self.assertEqual(dup.status_code, 409)

    def test_password_reset_honestly_reports_missing_smtp(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EMAIL_HOST", None)
            resp = self.client.post(
                "/api/users/password-reset/request/",
                {"email": "nobody@synthetic.local"},
                format="json",
            )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data["code"], "SMTP_NOT_CONFIGURED")

    def test_google_oidc_disabled_by_default_and_validates_claims_without_privilege_escalation(self):
        disabled = self.client.post("/api/users/google/login/", {"id_token": "x" * 30}, format="json")
        self.assertEqual(disabled.status_code, 503)
        self.assertEqual(disabled.data["code"], "GOOGLE_LOGIN_DISABLED")

        private_key, jwks = _make_rsa_jwk_pair()
        client_id = "synthetic-google-client.apps.googleusercontent.com"

        def make_token(**claims):
            base = {
                "iss": "https://accounts.google.com",
                "aud": client_id,
                "sub": "google-sub-123",
                "email": "googleuser@synthetic.local",
                "email_verified": True,
                "given_name": "Ana",
                "family_name": "Prueba",
                "exp": int(time()) + 300,
            }
            base.update(claims)
            return jwt.encode(base, private_key, algorithm="RS256", headers={"kid": "google-test-kid"})

        with patch.dict(os.environ, {"GOOGLE_OIDC_CLIENT_ID": client_id}), patch(
            "users.google_oidc._fetch_google_jwks", return_value=jwks
        ):
            # Rejects unverified email
            bad_email = self.client.post(
                "/api/users/google/login/",
                {"id_token": make_token(email_verified=False)},
                format="json",
            )
            self.assertEqual(bad_email.status_code, 401)

            # Rejects unauthorized redirect_uri (open redirect)
            bad_redirect = self.client.post(
                "/api/users/google/login/",
                {"id_token": make_token(), "redirect_uri": "https://evil.example/cb"},
                format="json",
            )
            self.assertEqual(bad_redirect.status_code, 401)

            # Valid login creates standard user with NO admin privileges
            ok = self.client.post(
                "/api/users/google/login/",
                {"id_token": make_token(), "redirect_uri": "http://localhost:3000/login"},
                format="json",
            )
            self.assertEqual(ok.status_code, 200)
            self.assertTrue(ok.data["created"])
            self.assertFalse(ok.data["user"]["is_superuser"])
            self.assertFalse(ok.data["user"]["is_staff"])

            # Second login associates existing account without duplicating
            again = self.client.post(
                "/api/users/google/login/",
                {"id_token": make_token()},
                format="json",
            )
            self.assertEqual(again.status_code, 200)
            self.assertFalse(again.data["created"])
            self.assertEqual(User.objects.filter(email="googleuser@synthetic.local").count(), 1)

