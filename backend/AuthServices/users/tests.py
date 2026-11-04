from django.contrib.auth.models import Group, Permission, User
from django.db import connection
from rest_framework.test import APITestCase

from .models import Tenant, TenantArea, TenantMembership


class TenantIdentityBoundaryTests(APITestCase):
    tenant_models = (Tenant, TenantArea, TenantMembership)

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
