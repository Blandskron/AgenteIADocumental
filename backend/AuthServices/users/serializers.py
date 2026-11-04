from django.contrib.auth.models import Group, Permission, User
from django.db import transaction
from django.db.models import F
from rest_framework import serializers
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from .models import Tenant, TenantArea, TenantGroup, TenantGroupPermission, TenantMembership, TenantUserGroup


TENANT_ROLE_PERMISSIONS = {
    "TENANT_ADMIN": [
        "tenant.manage",
        "tenant.users.create",
        "tenant.users.assign_area",
        "tenant.areas.manage",
        "documents.upload",
        "documents.view_all_tenant",
        "documents.download_assigned",
        "documents.assign",
        "documents.accept",
        "documents.reject",
        "documents.sign",
        "documents.delete",
        "documents.export",
    ],
    "LEADER": [
        "documents.upload",
        "documents.view_managed",
        "documents.download_assigned",
        "documents.assign",
        "documents.accept",
        "documents.reject",
        "documents.sign",
        "documents.export",
    ],
    "USER": [
        "documents.upload",
        "documents.view_assigned",
        "documents.download_assigned",
        "documents.accept",
        "documents.reject",
        "documents.sign",
    ],
}


def tenant_membership_payload(user):
    user_group_rows = TenantUserGroup.objects.select_related("group").filter(
        user_id=str(user.id), group__tenant_id=F("tenant_id")
    )
    group_names_by_tenant = {}
    group_ids_by_tenant = {}
    for row in user_group_rows:
        group_names_by_tenant.setdefault(row.tenant_id, []).append(row.group.name)
        group_ids_by_tenant.setdefault(row.tenant_id, []).append(row.group_id)

    group_permissions_by_tenant = {}
    permissions = TenantGroupPermission.objects.filter(group_id__in=[row.group_id for row in user_group_rows])
    for permission in permissions:
        tenant_id = next((row.tenant_id for row in user_group_rows if row.group_id == permission.group_id), None)
        if tenant_id:
            group_permissions_by_tenant.setdefault(tenant_id, set()).add(permission.permission_code)

    memberships = (
        TenantMembership.objects.select_related("tenant", "area")
        .filter(user_id=str(user.id), status="ACTIVE", tenant__status="ACTIVE")
        .order_by("role", "tenant__name")
    )
    payload = []
    for membership in memberships:
        area = membership.area if membership.area_id and membership.area.tenant_id == membership.tenant_id else None
        role_permissions = set(TENANT_ROLE_PERMISSIONS.get(membership.role, []))
        group_permissions = group_permissions_by_tenant.get(membership.tenant_id, set())
        payload.append({
            "membership_id": membership.membership_id,
            "tenant_id": membership.tenant_id,
            "tenant_name": membership.tenant.name,
            "area_id": area.pk if area else None,
            "area_name": area.name if area else None,
            "role": membership.role,
            "groups": group_names_by_tenant.get(membership.tenant_id, []),
            "group_ids": group_ids_by_tenant.get(membership.tenant_id, []),
            "permissions": sorted(role_permissions | group_permissions),
        })
    return payload


def active_membership(memberships):
    role_priority = {"TENANT_ADMIN": 0, "LEADER": 1, "USER": 2}
    if not memberships:
        return None
    return sorted(memberships, key=lambda item: role_priority.get(item["role"], 99))[0]


def serialize_user_profile(user):
    groups = list(user.groups.values_list("name", flat=True))
    permissions = list(user.get_all_permissions())
    memberships = tenant_membership_payload(user)
    active = active_membership(memberships)
    display_name = user.get_full_name() or user.username
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": display_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "is_superadmin": user.is_superuser,
        "groups": groups,
        "permissions": permissions,
        "tenant_memberships": memberships,
        "active_tenant_id": active["tenant_id"] if active else None,
        "active_area_id": active["area_id"] if active else None,
        "active_role": active["role"] if active else ("SUPERADMIN" if user.is_superuser else None),
        "active_permissions": active["permissions"] if active else ([] if not user.is_superuser else ["*"]),
        "roles": ["SUPERADMIN"] if user.is_superuser else [membership["role"] for membership in memberships] or groups,
    }


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        return cls.add_current_claims(super().get_token(user), user)

    @staticmethod
    def add_current_claims(token, user):
        profile = serialize_user_profile(user)
        token["user_id"] = profile["id"]
        token["username"] = profile["username"]
        token["email"] = profile["email"]
        token["first_name"] = profile["first_name"]
        token["last_name"] = profile["last_name"]
        token["display_name"] = profile["display_name"]
        token["is_staff"] = profile["is_staff"]
        token["is_superuser"] = profile["is_superuser"]
        token["is_superadmin"] = profile["is_superadmin"]
        token["groups"] = profile["groups"]
        token["permissions"] = profile["permissions"]
        token["roles"] = profile["roles"]
        token["tenant_memberships"] = profile["tenant_memberships"]
        token["active_tenant_id"] = profile["active_tenant_id"]
        token["active_area_id"] = profile["active_area_id"]
        token["active_role"] = profile["active_role"]
        token["active_permissions"] = profile["active_permissions"]
        token["grupos"] = profile["groups"]
        token["permisos"] = profile["permissions"]
        return token


class CurrentClaimsRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        user = User.objects.filter(pk=refresh[api_settings.USER_ID_CLAIM], is_active=True).first()
        if user is None or not constant_time_compare(
            str(refresh.get(api_settings.REVOKE_TOKEN_CLAIM, "")), get_md5_hash_password(user.password)
        ):
            raise InvalidToken("La sesión ya no es válida. Inicia sesión de nuevo.")

        access = MyTokenObtainPairSerializer.add_current_claims(AccessToken.for_user(user), user)
        return {"access": str(access)}


class UserSerializer(serializers.ModelSerializer):
    groups = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    group_names = serializers.SerializerMethodField(read_only=True)
    user_permissions = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)
    permission_ids = serializers.SerializerMethodField(read_only=True)
    permission_names = serializers.SerializerMethodField(read_only=True)
    role = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "is_staff",
            "is_superuser",
            "is_active",
            "role",
            "groups",
            "group_names",
            "user_permissions",
            "permission_ids",
            "permission_names",
        )
        extra_kwargs = {"password": {"write_only": True, "required": False}}

    def get_group_names(self, user):
        return list(user.groups.values_list("name", flat=True))

    def get_permission_names(self, user):
        return list(user.user_permissions.values_list("codename", flat=True))

    def get_permission_ids(self, user):
        return list(user.user_permissions.values_list("id", flat=True))

    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        permissions = validated_data.pop("user_permissions", [])
        role = validated_data.pop("role", None)
        self._apply_role_flags(validated_data, role)
        user = User.objects.create_user(**validated_data)
        self._set_groups(user, groups)
        self._set_permissions(user, permissions)
        return user

    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        permissions = validated_data.pop("user_permissions", None)
        role = validated_data.pop("role", None)
        self._apply_role_flags(validated_data, role)
        if "password" in validated_data:
            password = validated_data.pop("password")
            if password:
                instance.set_password(password)
        user = super().update(instance, validated_data)
        if groups is not None:
            self._set_groups(user, groups)
        if permissions is not None:
            self._set_permissions(user, permissions)
        return user

    def _apply_role_flags(self, data, role):
        if role == "super_admin":
            data["is_staff"] = True
            data["is_superuser"] = True
        elif role == "admin":
            data["is_staff"] = False
            data["is_superuser"] = False
        elif role == "ejecutivo":
            data["is_staff"] = False
            data["is_superuser"] = False

    def _set_groups(self, user, group_names):
        groups = [Group.objects.get_or_create(name=name)[0] for name in group_names]
        user.groups.set(groups)

    def _set_permissions(self, user, permission_ids):
        permissions = Permission.objects.filter(id__in=permission_ids)
        user.user_permissions.set(permissions)


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)
    model = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = Permission
        fields = ("id", "name", "codename", "app_label", "model")


class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)
    permission_ids = serializers.SerializerMethodField(read_only=True)
    permission_names = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Group
        fields = ("id", "name", "permissions", "permission_ids", "permission_names")

    def get_permission_names(self, group):
        return list(group.permissions.values_list("codename", flat=True))

    def get_permission_ids(self, group):
        return list(group.permissions.values_list("id", flat=True))

    def create(self, validated_data):
        permission_codenames = validated_data.pop("permissions", [])
        group = Group.objects.create(**validated_data)
        self._set_permissions(group, permission_codenames)
        return group

    def update(self, instance, validated_data):
        permission_codenames = validated_data.pop("permissions", None)
        group = super().update(instance, validated_data)
        if permission_codenames is not None:
            self._set_permissions(group, permission_codenames)
        return group

    def _set_permissions(self, group, permission_ids):
        permissions = Permission.objects.filter(id__in=permission_ids)
        group.permissions.set(permissions)


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ("tenant_id", "name", "tax_id", "status", "created_by_user_id", "metadata", "created_at", "updated_at")
        read_only_fields = ("tenant_id", "created_by_user_id", "created_at", "updated_at")


class TenantScopedSerializer(serializers.ModelSerializer):
    tenant_relation = None

    def validate(self, attrs):
        tenant = attrs.get("tenant", self.instance.tenant if self.instance else None)
        if self.instance and tenant.pk != self.instance.tenant_id:
            raise serializers.ValidationError({"tenant": "La empresa no se puede cambiar."})
        if self.tenant_relation:
            relation = attrs.get(self.tenant_relation, getattr(self.instance, self.tenant_relation, None))
            if relation is not None and relation.tenant_id != tenant.pk:
                raise serializers.ValidationError({self.tenant_relation: "Debe pertenecer a la misma empresa."})
        return attrs


class TenantAreaSerializer(TenantScopedSerializer):
    tenant_relation = "parent_area"

    class Meta:
        model = TenantArea
        fields = ("area_id", "tenant", "name", "parent_area", "metadata", "created_at", "updated_at")
        read_only_fields = ("area_id", "created_at", "updated_at")


class TenantMembershipSerializer(TenantScopedSerializer):
    tenant_relation = "area"
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    area_name = serializers.CharField(source="area.name", read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = TenantMembership
        fields = (
            "membership_id",
            "tenant",
            "tenant_name",
            "user_id",
            "area",
            "area_name",
            "role",
            "status",
            "created_by_user_id",
            "metadata",
            "permissions",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("membership_id", "created_by_user_id", "permissions", "created_at", "updated_at")

    def get_permissions(self, membership):
        return TENANT_ROLE_PERMISSIONS.get(membership.role, [])


class TenantUserProvisionSerializer(serializers.ModelSerializer):
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all())
    area = serializers.PrimaryKeyRelatedField(queryset=TenantArea.objects.all(), required=False, allow_null=True)
    role = serializers.ChoiceField(choices=tuple(TENANT_ROLE_PERMISSIONS))

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password", "tenant", "area", "role")
        extra_kwargs = {"password": {"write_only": True, "required": True, "trim_whitespace": False}}

    def validate(self, attrs):
        unexpected = self.initial_data.keys() - self.fields.keys()
        if unexpected:
            raise serializers.ValidationError({field: "Campo no permitido." for field in sorted(unexpected)})
        area = attrs.get("area")
        if area is not None and area.tenant_id != attrs["tenant"].pk:
            raise serializers.ValidationError({"area": "El área debe pertenecer a la empresa seleccionada."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tenant = validated_data.pop("tenant")
        area = validated_data.pop("area", None)
        role = validated_data.pop("role")
        user = User.objects.create_user(**validated_data)
        return TenantMembership.objects.create(
            tenant=tenant, area=area, role=role, user_id=str(user.pk),
            created_by_user_id=str(self.context["request"].user.pk),
        )


class TenantGroupPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantGroupPermission
        fields = ("group", "permission_code", "created_at")
        read_only_fields = ("created_at",)


class TenantGroupSerializer(TenantScopedSerializer):
    permissions = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    permission_codes = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TenantGroup
        fields = (
            "group_id",
            "tenant",
            "name",
            "description",
            "is_system",
            "metadata",
            "permissions",
            "permission_codes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("group_id", "permission_codes", "created_at", "updated_at")

    def get_permission_codes(self, group):
        return list(TenantGroupPermission.objects.filter(group=group).values_list("permission_code", flat=True))

    @transaction.atomic
    def create(self, validated_data):
        permissions = validated_data.pop("permissions", [])
        group = TenantGroup.objects.create(**validated_data)
        self._set_permissions(group, permissions)
        return group

    @transaction.atomic
    def update(self, instance, validated_data):
        permissions = validated_data.pop("permissions", None)
        group = super().update(instance, validated_data)
        if permissions is not None:
            self._set_permissions(group, permissions)
        return group

    def _set_permissions(self, group, permissions):
        TenantGroupPermission.objects.filter(group=group).delete()
        for permission in permissions:
            TenantGroupPermission.objects.create(group=group, permission_code=permission)


class TenantUserGroupSerializer(TenantScopedSerializer):
    tenant_relation = "group"
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = TenantUserGroup
        fields = ("tenant", "user_id", "group", "group_name", "created_at")
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and attrs.get("user_id", self.instance.user_id) != self.instance.user_id:
            raise serializers.ValidationError({"user_id": "El usuario de la asignación no se puede cambiar."})
        return attrs

    @staticmethod
    def _lock_membership(tenant, user_id):
        if not TenantMembership.objects.select_for_update().filter(tenant=tenant, user_id=user_id).first():
            raise serializers.ValidationError({"user_id": "El usuario debe pertenecer a la misma empresa."})

    @transaction.atomic
    def create(self, validated_data):
        self._lock_membership(validated_data["tenant"], validated_data["user_id"])
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        self._lock_membership(instance.tenant_id, instance.user_id)
        return super().update(instance, validated_data)
