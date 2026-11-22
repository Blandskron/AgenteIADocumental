from unittest.mock import patch

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


class OllamaIntegrationApiTests(APITestCase):
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

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Ollama Org")
        self.admin = User.objects.create_user("ollama_admin", "oa@synthetic.local", "StrongPass!23456")
        self.user = User.objects.create_user("ollama_user", "ou@synthetic.local", "StrongPass!23456")
        TenantMembership.objects.create(tenant=self.tenant, user_id=str(self.admin.id), role="TENANT_ADMIN")
        TenantMembership.objects.create(tenant=self.tenant, user_id=str(self.user.id), role="USER")

    def test_regular_user_cannot_manage_provider_or_pull_models(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/integrations/ai/provider/").status_code, 403)
        self.assertEqual(self.client.patch("/api/integrations/ai/provider/", {"active_provider": "ollama"}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/integrations/ollama/pull/", {"model": "qwen2.5:3b"}, format="json").status_code, 403)

    @patch("users.ollama_integrations._ollama_http_json")
    def test_admin_switches_provider_lists_tests_and_enforces_allowlist_and_ssrf(self, mock_http):
        self.client.force_authenticate(self.admin)

        # Default active provider is groq
        res = self.client.get("/api/integrations/ai/provider/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["active_provider"], "groq")

        # Switch to ollama
        sw = self.client.patch("/api/integrations/ai/provider/", {"active_provider": "ollama"}, format="json")
        self.assertEqual(sw.status_code, 200)
        self.assertEqual(sw.data["active_provider"], "ollama")

        # Reject SSRF external base_url
        bad_url = self.client.patch(
            "/api/integrations/ollama/",
            {"base_url": "http://169.254.169.254/latest"},
            format="json",
        )
        self.assertEqual(bad_url.status_code, 400)

        # Update valid local settings
        ok_cfg = self.client.patch(
            "/api/integrations/ollama/",
            {"base_url": "http://127.0.0.1:11434", "model": "qwen2.5:3b", "params": {"max_tokens": 1024}},
            format="json",
        )
        self.assertEqual(ok_cfg.status_code, 200)
        self.assertEqual(ok_cfg.data["model"], "qwen2.5:3b")

        # Reject unapproved model download
        bad_pull = self.client.post(
            "/api/integrations/ollama/pull/",
            {"model": "untrusted/huge-70b"},
            format="json",
        )
        self.assertEqual(bad_pull.status_code, 400)
        self.assertEqual(bad_pull.data["code"], "MODEL_NOT_APPROVED")

        # List models + test connection via mocked Ollama HTTP
        mock_http.side_effect = [
            (200, {"models": [{"name": "qwen2.5:3b", "size": 1900000000}]}),
            (200, {"choices": [{"message": {"content": "ok"}}]}),
        ]
        models_res = self.client.get("/api/integrations/ollama/models/")
        self.assertEqual(models_res.status_code, 200)
        self.assertTrue(models_res.data["reachable"])
        self.assertEqual(models_res.data["installed"][0]["name"], "qwen2.5:3b")

        test_res = self.client.post("/api/integrations/ollama/test/", {"model": "qwen2.5:3b"}, format="json")
        self.assertEqual(test_res.status_code, 200)
        self.assertEqual(test_res.data["result"], "ok")

