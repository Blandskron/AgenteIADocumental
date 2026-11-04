from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .login_protection import _consume
from .models import LoginAttemptBudget, Tenant, TenantArea, TenantGroup, TenantGroupPermission, TenantMembership, TenantUserGroup
from .serializers import MyTokenObtainPairSerializer, ProfileMembershipSerializer, UserProfileSerializer, tenant_membership_payload


class TenantIdentityBoundaryTests(APITestCase):
    tenant_models = (Tenant, TenantArea, TenantMembership, TenantGroup, TenantGroupPermission, TenantUserGroup)

    @classmethod
    def setUpClass(cls):
        # Django migrations do not create the shared, unmanaged tenant tables.
        with connection.schema_editor() as schema:
            for model in cls.tenant_models:
                schema.create_model(model)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.schema_editor() as schema:
            for model in reversed(cls.tenant_models):
                schema.delete_model(model)

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Empresa A")
        self.other_tenant = Tenant.objects.create(name="Empresa B")
        self.admin = User.objects.create_user(username="tenant-admin")
        self.member = User.objects.create_user(username="tenant-member")
        self.victim = User.objects.create_superuser(username="global-admin")
        self.membership = TenantMembership.objects.create(
            tenant=self.tenant, user_id=str(self.admin.pk), role="TENANT_ADMIN"
        )
        TenantMembership.objects.create(tenant=self.tenant, user_id=str(self.member.pk), role="USER")
        self.client.force_authenticate(self.admin)

    def test_profile_matches_documented_fields(self):
        response = self.client.get("/api/users/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), set(UserProfileSerializer().fields))
        self.assertEqual(
            set(response.data["tenant_memberships"][0]), set(ProfileMembershipSerializer().fields)
        )

    def test_tenant_admin_cannot_create_global_superuser(self):
        for index, privilege in enumerate(({"role": "super_admin"}, {"is_superuser": True})):
            with self.subTest(privilege=privilege):
                username = f"injected-{index}"
                response = self.client.post(
                    "/api/users/crud/", {"username": username, **privilege}, format="json"
                )
                self.assertEqual(response.status_code, 403)
                self.assertFalse(User.objects.filter(username=username).exists())

    def test_tenant_admin_cannot_attach_existing_global_identity(self):
        response = self.client.post(
            "/api/users/tenant-memberships/",
            {"tenant": self.tenant.pk, "user_id": str(self.victim.pk), "role": "USER"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TenantMembership.objects.filter(user_id=str(self.victim.pk)).exists())

    def test_tenant_admin_cannot_replace_membership_identity(self):
        response = self.client.patch(
            f"/api/users/tenant-memberships/{self.membership.pk}/",
            {"user_id": str(self.victim.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.user_id, str(self.admin.pk))

    def test_tenant_admin_cannot_mutate_global_account_even_if_linked(self):
        TenantMembership.objects.create(tenant=self.tenant, user_id=str(self.victim.pk), role="USER")
        url = f"/api/users/crud/{self.victim.pk}/"
        original_password = self.victim.password
        self.assertEqual(self.client.patch(url, {"password": "new-password"}, format="json").status_code, 403)
        self.assertEqual(self.client.put(url, {"username": "changed"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.victim.refresh_from_db()
        self.assertEqual(self.victim.password, original_password)

    def test_staff_tenant_admin_cannot_grant_permissions_through_global_group(self):
        self.admin.is_staff = True
        self.admin.save(update_fields=["is_staff"])
        group = Group.objects.create(name="Staff sin permisos de identidad")
        self.admin.groups.add(group)
        permission = Permission.objects.get(content_type__app_label="auth", codename="change_user")
        url = f"/api/users/groups/{group.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, {"permissions": [permission.pk]}, format="json").status_code, 403)
        self.assertFalse(group.permissions.exists())

    def test_tenant_admin_can_read_members_and_change_membership_role(self):
        self.assertEqual(self.client.get(f"/api/users/crud/{self.member.pk}/").status_code, 200)
        response = self.client.patch(
            f"/api/users/tenant-memberships/{self.membership.pk}/", {"role": "LEADER"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.role, "LEADER")

    def test_superadmin_can_manage_global_identity(self):
        self.client.force_authenticate(self.victim)
        response = self.client.post(
            "/api/users/crud/", {"username": "new-global-admin", "role": "super_admin"}, format="json"
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="new-global-admin")
        self.assertTrue(user.is_superuser)
        self.assertEqual(self.client.delete(f"/api/users/crud/{user.pk}/").status_code, 204)

    def provision(self, **overrides):
        return self.client.post(
            "/api/users/tenant-memberships/provision/",
            {
                "tenant": self.tenant.pk,
                "username": "new-member",
                "password": "password-for-test",
                "role": "USER",
                **overrides,
            },
            format="json",
        )

    def test_tenant_admin_can_provision_new_member(self):
        area = TenantArea.objects.create(tenant=self.tenant, name="Operaciones")
        response = self.provision(area=area.pk)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="new-member")
        self.assertTrue(user.check_password("password-for-test"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        membership = TenantMembership.objects.get(user_id=str(user.pk))
        self.assertEqual(membership.tenant_id, self.tenant.pk)
        self.assertEqual(membership.area_id, area.pk)

    def test_provision_rejects_global_flags_or_existing_subject(self):
        for extra in (
            {"is_superuser": True}, {"role": "super_admin"}, {"groups": ["SUPERADMIN"]},
            {"user_permissions": [1]}, {"user_id": str(self.victim.pk)}, {"username": self.victim.username},
        ):
            with self.subTest(extra=extra):
                self.assertEqual(self.provision(**extra).status_code, 400)
                self.assertFalse(User.objects.filter(username="new-member").exists())

    def test_provision_rejects_foreign_tenant_and_area(self):
        area = TenantArea.objects.create(tenant=self.other_tenant, name="Externa")
        self.assertEqual(self.provision(tenant=self.other_tenant.pk).status_code, 403)
        self.assertEqual(self.provision(area=area.pk).status_code, 400)
        self.assertFalse(User.objects.filter(username="new-member").exists())

    def test_superadmin_can_provision_in_suspended_tenant(self):
        self.other_tenant.status = "SUSPENDED"
        self.other_tenant.save(update_fields=["status"])
        self.client.force_authenticate(self.victim)
        self.assertEqual(self.provision(tenant=self.other_tenant.pk).status_code, 201)

    def test_area_and_group_cannot_move_between_tenants(self):
        area = TenantArea.objects.create(tenant=self.tenant, name="Área")
        group = TenantGroup.objects.create(tenant=self.tenant, name="Grupo")
        for resource, instance in (("tenant-areas", area), ("tenant-groups", group)):
            with self.subTest(resource=resource):
                url = f"/api/users/{resource}/{instance.pk}/"
                payload = {"tenant": self.other_tenant.pk, "name": instance.name}
                self.assertEqual(self.client.patch(url, payload, format="json").status_code, 400)
                self.assertEqual(self.client.put(url, payload, format="json").status_code, 400)
                instance.refresh_from_db()
                self.assertEqual(instance.tenant_id, self.tenant.pk)

    def test_foreign_area_rejected_in_hierarchy_and_membership(self):
        foreign_area = TenantArea.objects.create(tenant=self.other_tenant, name="Externa")
        response = self.client.post(
            "/api/users/tenant-areas/",
            {"tenant": self.tenant.pk, "name": "Área", "parent_area": foreign_area.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            f"/api/users/tenant-memberships/{self.membership.pk}/",
            {"area": foreign_area.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_group_assignment_requires_same_tenant_and_membership(self):
        group = TenantGroup.objects.create(tenant=self.tenant, name="Chat")
        foreign = TenantGroup.objects.create(tenant=self.other_tenant, name="Externo")
        url = "/api/users/tenant-user-groups/"
        payload = {"tenant": self.tenant.pk, "group": group.pk, "user_id": str(self.member.pk)}
        self.assertEqual(self.client.post(url, {**payload, "group": foreign.pk}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {**payload, "user_id": str(self.victim.pk)}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, payload, format="json").status_code, 201)
        assignment = TenantUserGroup.objects.get(group=group)
        self.assertEqual(
            self.client.patch(f"{url}{assignment.pk}/", {"tenant": self.other_tenant.pk}, format="json").status_code,
            400,
        )

    def test_legacy_foreign_relationships_do_not_enter_claims(self):
        area = TenantArea.objects.create(tenant=self.other_tenant, name="Externa")
        self.membership.area = area
        self.membership.save(update_fields=["area"])
        local = TenantGroup.objects.create(tenant=self.tenant, name="Local")
        foreign = TenantGroup.objects.create(tenant=self.other_tenant, name="Externo")
        for group, code in ((local, "use_chat"), (foreign, "manage_documents")):
            TenantGroupPermission.objects.create(group=group, permission_code=code)
            TenantUserGroup.objects.create(tenant=self.tenant, group=group, user_id=str(self.admin.pk))
        claims = tenant_membership_payload(self.admin)[0]
        self.assertEqual(claims["group_ids"], [local.pk])
        self.assertIn("use_chat", claims["permissions"])
        self.assertNotIn("manage_documents", claims["permissions"])
        self.assertIsNone(claims["area_id"])

    def test_deleting_membership_revokes_group_assignments(self):
        membership = TenantMembership.objects.get(tenant=self.tenant, user_id=str(self.member.pk))
        group = TenantGroup.objects.create(tenant=self.tenant, name="Chat")
        TenantUserGroup.objects.create(tenant=self.tenant, group=group, user_id=membership.user_id)
        self.assertEqual(self.client.delete(f"/api/users/tenant-memberships/{membership.pk}/").status_code, 204)
        self.assertFalse(TenantUserGroup.objects.filter(group=group).exists())
        TenantMembership.objects.create(tenant=self.tenant, user_id=str(self.member.pk), role="USER")
        self.assertEqual(tenant_membership_payload(self.member)[0]["group_ids"], [])

    def test_deleting_local_objects_cannot_modify_legacy_foreign_rows(self):
        area = TenantArea.objects.create(tenant=self.tenant, name="Área")
        child = TenantArea.objects.create(tenant=self.other_tenant, name="Externa", parent_area=area)
        group = TenantGroup.objects.create(tenant=self.tenant, name="Grupo")
        assignment = TenantUserGroup.objects.create(
            tenant=self.other_tenant, group=group, user_id=str(self.member.pk)
        )
        self.assertEqual(self.client.delete(f"/api/users/tenant-areas/{area.pk}/").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/users/tenant-groups/{group.pk}/").status_code, 403)
        self.assertTrue(TenantArea.objects.filter(pk=child.pk, parent_area=area).exists())
        self.assertTrue(TenantUserGroup.objects.filter(pk=assignment.pk).exists())

    def test_suspended_tenant_admin_cannot_read_or_mutate_tenant_resources(self):
        self.tenant.status = "SUSPENDED"
        self.tenant.save(update_fields=["status"])
        self.assertEqual(self.client.get("/api/users/tenant-areas/").status_code, 403)
        self.assertEqual(self.provision().status_code, 403)
        self.assertEqual(tenant_membership_payload(self.admin), [])

    def refresh_session(self, token):
        return self.client.post("/api/users/token/refresh/", {"refresh": str(token)}, format="json")

    def test_refresh_recomputes_roles_and_tenant_permissions(self):
        token = MyTokenObtainPairSerializer.get_token(self.admin)
        self.assertEqual(token["active_role"], "TENANT_ADMIN")
        self.membership.role = "USER"
        self.membership.save(update_fields=["role"])
        response = self.refresh_session(token)
        self.assertEqual(response.status_code, 200)
        access = AccessToken(response.data["access"])
        self.assertEqual(access["active_role"], "USER")
        self.assertEqual(access["exp"] - access["iat"], 600)
        self.assertNotIn("tenant.manage", access["active_permissions"])

        self.tenant.status = "SUSPENDED"
        self.tenant.save(update_fields=["status"])
        access = AccessToken(self.refresh_session(token).data["access"])
        self.assertEqual(access["tenant_memberships"], [])
        self.assertIsNone(access["active_tenant_id"])

    def test_refresh_rejects_password_change_and_inactive_account(self):
        token = MyTokenObtainPairSerializer.get_token(self.admin)
        self.admin.set_password("new-password-for-test")
        self.admin.save(update_fields=["password"])
        self.assertEqual(self.refresh_session(token).status_code, 401)
        token = MyTokenObtainPairSerializer.get_token(self.admin)
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        self.assertEqual(self.refresh_session(token).status_code, 401)

    def test_refresh_rejects_logout_legacy_and_access_tokens(self):
        token = MyTokenObtainPairSerializer.get_token(self.admin)
        self.assertEqual(self.refresh_session(token.access_token).status_code, 401)
        response = self.client.post("/api/users/logout/", {"refresh": str(token)}, format="json")
        self.assertEqual(response.status_code, 205)
        self.assertEqual(self.refresh_session(token).status_code, 401)
        legacy = MyTokenObtainPairSerializer.get_token(self.admin)
        del legacy["hash_password"]
        self.assertEqual(self.refresh_session(legacy).status_code, 401)
        expired = MyTokenObtainPairSerializer.get_token(self.admin)
        expired["exp"] = 1
        self.assertEqual(self.refresh_session(expired).status_code, 401)

    def test_provision_rejects_weak_password_before_creating_identity(self):
        for password in ("12345678", 31415926.25):
            response = self.provision(password=password)
            self.assertEqual(response.status_code, 400)
            self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(username="new-member").exists())

    def test_password_is_checked_against_normalized_username(self):
        response = self.provision(username="ｚｑｋｆｊｐｖｍｘ", password="zqkfjpvmx")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)

    def test_global_password_validation_uses_effective_identity(self):
        self.client.force_authenticate(self.victim)
        response = self.client.post(
            "/api/users/crud/", {"username": "synthetic", "password": "password"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="synthetic").exists())
        self.member.set_password("previous-strong-password")
        self.member.save(update_fields=["password"])
        url = f"/api/users/crud/{self.member.pk}/"
        response = self.client.patch(
            url, {"username": "synthetic-user-new", "password": "synthetic-user-new"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.member.refresh_from_db()
        self.assertEqual(self.member.username, "tenant-member")
        self.assertTrue(self.member.check_password("previous-strong-password"))
        response = self.client.patch(url, {"password": " stronger-passphrase "}, format="json")
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password(" stronger-passphrase "))

    def test_self_password_change_rejects_weak_input_and_revokes_refresh(self):
        old_password = "previous-strong-password"
        self.admin.set_password(old_password)
        self.admin.save(update_fields=["password"])
        token = MyTokenObtainPairSerializer.get_token(self.admin)
        url = "/api/users/change-password/"
        for payload in (
            {"old_password": old_password, "new_password": "password"},
            {"old_password": old_password, "new_password": ["not", "a", "string"]},
            {"old_password": "incorrect", "new_password": " stronger-passphrase "},
        ):
            response = self.client.post(url, payload, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIsInstance(response.data["error"], str)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(old_password))
        response = self.client.post(
            url, {"old_password": old_password, "new_password": " stronger-passphrase "}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(" stronger-passphrase "))
        self.assertEqual(self.refresh_session(token).status_code, 401)
    @patch("users.views.authenticate", return_value=None)
    @patch("users.login_protection.time", return_value=120)
    def test_login_limit_is_shared_across_origins_and_resets_next_window(self, clock, authenticate):
        path = "/api/users/login/"
        for index in range(8):
            payload = {"username": "Demo" if index % 2 else "demo", "password": "incorrect"}
            response = self.client.post(path, payload, format="json", REMOTE_ADDR=f"192.0.2.{index + 1}")
            self.assertEqual(response.status_code, 400)
        payload = {"username": "demo", "password": "incorrect"}
        response = self.client.post(path, payload, format="json", REMOTE_ADDR="192.0.2.20")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertEqual(authenticate.call_count, 8)
        clock.return_value = 180
        self.assertEqual(self.client.post(path, payload, format="json").status_code, 400)

    @patch("users.views.authenticate", return_value=None)
    @patch("users.login_protection.time", return_value=120)
    def test_origin_limit_ignores_forged_forwarded_address(self, _clock, authenticate):
        for index in range(31):
            response = self.client.post(
                "/api/users/login/", {"username": f"example-{index}", "password": "incorrect"},
                format="json", HTTP_X_FORWARDED_FOR=f"192.0.2.{index + 1}", REMOTE_ADDR="192.0.2.100",
            )
            self.assertEqual(response.status_code, 400 if index < 30 else 429)
        self.assertEqual(authenticate.call_count, 30)

    @patch("users.views.authenticate", return_value=None)
    @patch("users.login_protection.time", return_value=120)
    def test_admin_form_shares_login_budget_and_logs_no_credentials(self, _clock, _authenticate):
        username, password = "unique-audit-subject", "unique-secret-synthetic"
        with self.assertLogs("blandskron.auth.audit", level="INFO") as audit:
            for _ in range(8):
                self.client.post("/api/users/login/", {"username": username, "password": password}, format="json")
            response = self.client.post("/admin/login/", {"username": username, "password": password})
        self.assertContains(response, "Demasiados intentos")
        self.assertIn('"channel": "django_admin"', audit.output[-1])
        for entry in audit.output:
            self.assertNotIn(username, entry)
            self.assertNotIn(password, entry)
        self.assertTrue(all(len(key) == 64 for key in LoginAttemptBudget.objects.values_list("key", flat=True)))


class LoginBudgetConcurrencyTests(TransactionTestCase):
    def test_parallel_connections_cannot_exceed_budget(self):
        def attempt(_index):
            try:
                return _consume("account", "parallel-fixture", 2, 8)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=12) as workers:
            outcomes = list(workers.map(attempt, range(12)))

        self.assertEqual(sum(outcomes), 8)
        self.assertEqual(LoginAttemptBudget.objects.get().attempts, 8)
