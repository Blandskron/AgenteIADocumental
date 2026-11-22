from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog
from .views import tenant_admin_ids

SENSITIVE_KEYS = frozenset(
    {"api_key", "password", "secret", "token", "access", "refresh", "authorization", "secrets_encrypted"}
)


def sanitize_audit_metadata(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}
    clean = {}
    for key, value in metadata.items():
        if str(key).strip().lower() in SENSITIVE_KEYS:
            continue
        clean[str(key)] = sanitize_audit_metadata(value) if isinstance(value, dict) else value
    return clean


def record_audit_log(
    *,
    action: str,
    resource_type: str,
    actor_user_id: str | int | None = None,
    tenant_id: str | None = None,
    resource_id: str | None = None,
    target_user_id: str | int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        tenant_id=tenant_id,
        actor_user_id=str(actor_user_id) if actor_user_id is not None else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        target_user_id=str(target_user_id) if target_user_id is not None else None,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:256] or None,
        metadata=sanitize_audit_metadata(metadata),
    )


class AuditLogItemSerializer(serializers.Serializer):
    audit_id = serializers.CharField()
    tenant_id = serializers.CharField(allow_null=True)
    actor_user_id = serializers.CharField(allow_null=True)
    action = serializers.CharField()
    resource_type = serializers.CharField()
    resource_id = serializers.CharField(allow_null=True)
    target_user_id = serializers.CharField(allow_null=True)
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()


class AuditLogListResponseSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    items = AuditLogItemSerializer(many=True)


class AuditLogListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auditoría"],
        responses={200: AuditLogListResponseSerializer},
    )
    def get(self, request):
        user = request.user
        admin_tenants = tenant_admin_ids(user)
        if not user.is_superuser and not admin_tenants:
            raise PermissionDenied("Solo administradores pueden consultar los registros de auditoría.")

        qs = AuditLog.objects.all().order_by("-created_at")
        if not user.is_superuser:
            qs = qs.filter(tenant_id__in=admin_tenants)

        action_filter = (request.query_params.get("action") or "").strip()
        if action_filter:
            qs = qs.filter(action=action_filter)
        resource_filter = (request.query_params.get("resource_type") or "").strip()
        if resource_filter:
            qs = qs.filter(resource_type=resource_filter)

        try:
            limit = max(1, min(100, int(request.query_params.get("limit", 25))))
            offset = max(0, int(request.query_params.get("offset", 0)))
        except ValueError:
            limit, offset = 25, 0

        total = qs.count()
        rows = list(qs[offset : offset + limit])
        items = [
            {
                "audit_id": row.audit_id,
                "tenant_id": row.tenant_id,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "target_user_id": row.target_user_id,
                "metadata": sanitize_audit_metadata(row.metadata),
                "created_at": row.created_at,
            }
            for row in rows
        ]
        return Response(
            {"total": total, "limit": limit, "offset": offset, "items": items},
            status=status.HTTP_200_OK,
        )

