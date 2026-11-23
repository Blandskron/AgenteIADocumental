from django.contrib.auth.models import User
from django.db import connection
from rest_framework.test import APITestCase

from users.audit_logs import record_audit_log
from users.cookie_session import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME
from users.models import (
    AuditLog,
    Tenant,
    TenantArea,
    TenantGroup,
    TenantGroupPermission,
    TenantMembership,
    TenantUserGroup,
)


class HardeningSessionAndAuditTests(APITestCase):
    unmanaged_models = (
        Tenant,
        TenantArea,
        TenantMembership,
        TenantGroup,
        TenantGroupPermission,
        TenantUserGroup,
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
        self.tenant_a = Tenant.objects.create(name="Audit Org A")
        self.tenant_b = Tenant.objects.create(name="Audit Org B")
        self.admin_a = User.objects.create_user("audit_admin_a", "aa@synthetic.local", "StrongPass!23456")
        self.user_a = User.objects.create_user("audit_user_a", "ua@synthetic.local", "StrongPass!23456")
        TenantMembership.objects.create(tenant=self.tenant_a, user_id=str(self.admin_a.id), role="TENANT_ADMIN")
        TenantMembership.objects.create(tenant=self.tenant_a, user_id=str(self.user_a.id), role="USER")

    def test_audit_log_redacts_secrets_and_enforces_tenant_isolation(self):
        record_audit_log(
            action="ai_settings_write",
            resource_type="tenant_integration",
            actor_user_id=self.admin_a.id,
            tenant_id=self.tenant_a.tenant_id,
            metadata={"provider": "groq", "api_key": "must-never-be-stored", "password": "secret"},
        )
        record_audit_log(
            action="ai_settings_write",
            resource_type="tenant_integration",
            actor_user_id=999,
            tenant_id=self.tenant_b.tenant_id,
            metadata={"provider": "groq"},
        )

        # Regular user gets 403
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get("/api/audit-logs/").status_code, 403)

        # Tenant admin sees only tenant_a logs with zero secret fields
        self.client.force_authenticate(self.admin_a)
        resp = self.client.get("/api/audit-logs/?action=ai_settings_write")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total"], 1)
        item = resp.data["items"][0]
        self.assertEqual(item["tenant_id"], self.tenant_a.tenant_id)
        self.assertNotIn("api_key", item["metadata"])
        self.assertNotIn("password", item["metadata"])
        self.assertNotIn("must-never-be-stored", str(resp.data))

    def test_cookie_session_sets_httponly_cookies_and_returns_csrf_without_tokens_in_body(self):
        resp = self.client.post(
            "/api/users/session/login/",
            {"username": "audit_admin_a", "password": "StrongPass!23456"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["authenticated"])
        self.assertTrue(resp.data["csrf_token"])
        self.assertNotIn("access", resp.data)
        self.assertNotIn("refresh", resp.data)
        self.assertTrue(resp.cookies[ACCESS_COOKIE_NAME]["httponly"])
        self.assertTrue(resp.cookies[REFRESH_COOKIE_NAME]["httponly"])
        self.assertEqual(resp.cookies[ACCESS_COOKIE_NAME]["samesite"], "Lax")

        # Refresh using HttpOnly cookie
        refresh_resp = self.client.post("/api/users/session/refresh/", {}, format="json")
        self.assertEqual(refresh_resp.status_code, 200)
        self.assertTrue(refresh_resp.data["authenticated"])
        self.assertTrue(refresh_resp.cookies[ACCESS_COOKIE_NAME]["httponly"])
        self.assertTrue(AuditLog.objects.filter(action="auth.cookie_login", actor_user_id=str(self.admin_a.id)).exists())

    def test_cookie_session_login_enforces_throttling(self):
        from unittest.mock import patch

        with patch("users.cookie_session.login_retry_after", return_value=45):
            throttled = self.client.post(
                "/api/users/session/login/",
                {"username": "audit_admin_a", "password": "WrongPassword!"},
                format="json",
            )
        self.assertEqual(throttled.status_code, 429)

