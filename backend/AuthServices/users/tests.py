from django.contrib.auth.models import Group, Permission, User
from django.db import connection
from rest_framework.test import APITestCase

from .models import Tenant, TenantArea, TenantGroup, TenantGroupPermission, TenantMembership, TenantUserGroup
from .serializers import tenant_membership_payload


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
