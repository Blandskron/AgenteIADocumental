import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from rest_framework.test import APITestCase

from users.models import (
    Tenant,
    TenantArea,
    TenantGroup,
    TenantGroupPermission,
    TenantIntegration,
    TenantMembership,
    TenantUserGroup,
)
from users.secrets_cipher import SecretsCipher


SYNTHETIC_MASTER_KEY = "synthetic-master-key-r103-0123456789abcdef!"
SYNTHETIC_GROQ_KEY = "synthetic-groq-secret-value-99999999"


class GroqIntegrationApiTests(APITestCase):
    unmanaged_models = (
        Tenant,
        TenantArea,
        TenantMembership,
        TenantGroup,
        TenantGroupPermission,
        TenantUserGroup,
        TenantIntegration,
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

    def setUp(self):
        self.tenant_a = Tenant.objects.create(name="Empresa Sintetica A")
        self.tenant_b = Tenant.objects.create(name="Empresa Sintetica B")
        self.admin_a = User.objects.create_user("groq_admin_a", "admin_a@synthetic.local", "StrongPass!23456")
        self.admin_b = User.objects.create_user("groq_admin_b", "admin_b@synthetic.local", "StrongPass!23456")
        self.user_a = User.objects.create_user("groq_user_a", "user_a@synthetic.local", "StrongPass!23456")
        TenantMembership.objects.create(tenant=self.tenant_a, user_id=str(self.admin_a.id), role="TENANT_ADMIN")
        TenantMembership.objects.create(tenant=self.tenant_b, user_id=str(self.admin_b.id), role="TENANT_ADMIN")
        TenantMembership.objects.create(tenant=self.tenant_a, user_id=str(self.user_a.id), role="USER")

    def test_regular_user_receives_403_on_all_endpoints(self):
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get("/api/integrations/groq/").status_code, 403)
        self.assertEqual(self.client.patch("/api/integrations/groq/", {"model": "llama-3.3-70b-versatile"}, format="json").status_code, 403)
        self.assertEqual(self.client.put("/api/integrations/groq/credentials/", {"api_key": SYNTHETIC_GROQ_KEY}, format="json").status_code, 403)
        self.assertEqual(self.client.delete("/api/integrations/groq/credentials/").status_code, 403)
        self.assertEqual(self.client.get("/api/integrations/groq/models/").status_code, 403)
        self.assertEqual(self.client.post("/api/integrations/groq/test/", {}, format="json").status_code, 403)

    @patch.dict(os.environ, {"SECRETS_ENCRYPTION_KEY": SYNTHETIC_MASTER_KEY, "SECRETS_KEY_ID": "v1"})
    def test_put_patch_get_delete_lifecycle_and_tenant_isolation_with_zero_secret_leak(self):
        self.client.force_authenticate(self.admin_a)

        # Initially not configured
        initial = self.client.get("/api/integrations/groq/")
        self.assertEqual(initial.status_code, 200)
        self.assertFalse(initial.data["configured"])
        self.assertEqual(initial.data["status"], "not_configured")
        self.assertIsNone(initial.data["key_fingerprint"])

        # Save credentials
        with self.assertLogs("blandskron.auth.audit", level="INFO") as logs:
            put_resp = self.client.put(
                "/api/integrations/groq/credentials/",
                {"api_key": SYNTHETIC_GROQ_KEY},
                format="json",
            )
        self.assertEqual(put_resp.status_code, 200)
        self.assertTrue(put_resp.data["configured"])
        self.assertEqual(put_resp.data["status"], "ready_to_test")
        self.assertEqual(put_resp.data["key_fingerprint"], SecretsCipher.fingerprint(SYNTHETIC_GROQ_KEY))
        self.assertNotIn(SYNTHETIC_GROQ_KEY, str(put_resp.data))
        self.assertNotIn(SYNTHETIC_GROQ_KEY, "\n".join(logs.output))

        # Stored row is encrypted with secrets1.v1.
        row = TenantIntegration.objects.get(tenant=self.tenant_a, provider="groq")
        self.assertTrue(row.secrets_encrypted.startswith("secrets1.v1."))
        self.assertNotIn(SYNTHETIC_GROQ_KEY, row.secrets_encrypted)

        # Patch non-sensitive params
        patch_resp = self.client.patch(
            "/api/integrations/groq/",
            {"model": "llama-3.1-8b-instant", "params": {"max_tokens": 1024, "temperature": 0.2}},
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.data["model"], "llama-3.1-8b-instant")
        self.assertEqual(patch_resp.data["params"]["max_tokens"], 1024)
        self.assertEqual(patch_resp.data["params"]["temperature"], 0.2)

        # Cross-tenant isolation: admin_b cannot see tenant_a's configuration
        self.client.force_authenticate(self.admin_b)
        other_resp = self.client.get("/api/integrations/groq/")
        self.assertEqual(other_resp.status_code, 200)
        self.assertFalse(other_resp.data["configured"])
        self.assertIsNone(other_resp.data["key_fingerprint"])

        # Revoke credentials as admin_a
        self.client.force_authenticate(self.admin_a)
        del_resp = self.client.delete("/api/integrations/groq/credentials/")
        self.assertEqual(del_resp.status_code, 200)
        self.assertFalse(del_resp.data["configured"])
        self.assertEqual(del_resp.data["status"], "not_configured")
        row.refresh_from_db()
        self.assertIsNone(row.secrets_encrypted)
        self.assertEqual(row.status, "DISABLED")

    @patch.dict(os.environ, {}, clear=False)
    def test_put_credentials_returns_503_when_encryption_key_missing(self):
        os.environ.pop("SECRETS_ENCRYPTION_KEY", None)
        self.client.force_authenticate(self.admin_a)
        resp = self.client.put(
            "/api/integrations/groq/credentials/",
            {"api_key": SYNTHETIC_GROQ_KEY},
            format="json",
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.data["code"], "ENCRYPTION_NOT_CONFIGURED")

    @patch.dict(os.environ, {"SECRETS_ENCRYPTION_KEY": SYNTHETIC_MASTER_KEY, "SECRETS_KEY_ID": "v1"})
    @patch("users.ai_integrations._groq_http_request")
    def test_models_proxy_and_connection_test_with_rate_limit(self, mock_http):
        self.client.force_authenticate(self.admin_a)
        self.client.put(
            "/api/integrations/groq/credentials/",
            {"api_key": SYNTHETIC_GROQ_KEY},
            format="json",
        )

        def fake_groq(method, path, api_key, payload=None):
            self.assertEqual(api_key, SYNTHETIC_GROQ_KEY)
            if method == "GET" and path == "/models":
                return 200, {
                    "data": [
                        {"id": "llama-3.3-70b-versatile", "active": True},
                        {"id": "whisper-large-v3", "active": True},
                        {"id": "llama-3.1-8b-instant", "active": True},
                    ]
                }
            if method == "POST" and path == "/chat/completions":
                self.assertEqual(payload["max_completion_tokens"], 1)
                self.assertEqual(payload["messages"], [{"role": "user", "content": "ping"}])
                return 200, {"choices": [{"message": {"content": "ok"}}]}
            return 500, {}

        mock_http.side_effect = fake_groq

        models_resp = self.client.get("/api/integrations/groq/models/")
        self.assertEqual(models_resp.status_code, 200)
        self.assertEqual(models_resp.data["result"], "ok")
        self.assertEqual(models_resp.data["models"], ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"])

        # 5 tests allowed per minute, 6th returns 429
        for _ in range(5):
            test_resp = self.client.post("/api/integrations/groq/test/", {}, format="json")
            self.assertEqual(test_resp.status_code, 200)
            self.assertEqual(test_resp.data["result"], "ok")
            self.assertNotIn(SYNTHETIC_GROQ_KEY, str(test_resp.data))

        throttled = self.client.post("/api/integrations/groq/test/", {}, format="json")
        self.assertEqual(throttled.status_code, 429)

        # Settings now reflect status == "connected"
        settings_resp = self.client.get("/api/integrations/groq/")
        self.assertEqual(settings_resp.data["status"], "connected")
        self.assertEqual(settings_resp.data["last_check"]["result"], "ok")
