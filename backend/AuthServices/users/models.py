import uuid

from django.db import models
from django.utils import timezone


def make_uuid():
    return str(uuid.uuid4())


class Tenant(models.Model):
    tenant_id = models.TextField(primary_key=True, default=make_uuid)
    name = models.TextField()
    tax_id = models.TextField(blank=True, null=True)
    status = models.TextField(default="ACTIVE")
    created_by_user_id = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "tenants"


class TenantArea(models.Model):
    area_id = models.TextField(primary_key=True, default=make_uuid)
    tenant = models.ForeignKey(Tenant, db_column="tenant_id", on_delete=models.CASCADE)
    name = models.TextField()
    parent_area = models.ForeignKey("self", db_column="parent_area_id", blank=True, null=True, on_delete=models.SET_NULL)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "tenant_areas"


class TenantMembership(models.Model):
    membership_id = models.TextField(primary_key=True, default=make_uuid)
    tenant = models.ForeignKey(Tenant, db_column="tenant_id", on_delete=models.CASCADE)
    user_id = models.TextField()
    area = models.ForeignKey(TenantArea, db_column="area_id", blank=True, null=True, on_delete=models.SET_NULL)
    role = models.TextField()
    status = models.TextField(default="ACTIVE")
    created_by_user_id = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "tenant_memberships"


class TenantGroup(models.Model):
    group_id = models.TextField(primary_key=True, default=make_uuid)
    tenant = models.ForeignKey(Tenant, db_column="tenant_id", on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField(blank=True, null=True)
    is_system = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "tenant_groups"


class TenantGroupPermission(models.Model):
    permission_id = models.TextField(primary_key=True, default=make_uuid)
    group = models.ForeignKey(TenantGroup, db_column="group_id", on_delete=models.CASCADE)
    permission_code = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "tenant_group_permissions"
        unique_together = (("group", "permission_code"),)


class TenantUserGroup(models.Model):
    user_group_id = models.TextField(primary_key=True, default=make_uuid)
    tenant = models.ForeignKey(Tenant, db_column="tenant_id", on_delete=models.CASCADE)
    user_id = models.TextField()
    group = models.ForeignKey(TenantGroup, db_column="group_id", on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "tenant_user_groups"
        unique_together = (("tenant", "user_id", "group"),)
