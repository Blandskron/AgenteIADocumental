from django.db import IntegrityError, OperationalError
from rest_framework.exceptions import APIException


RELATION_CONSTRAINTS = frozenset(
    {
        "tenant_assignments_group_tenant_fk",
        "tenant_assignments_membership_fk",
        "tenant_areas_parent_tenant_fk",
        "tenant_areas_tenant_id_fkey",
        "tenant_memberships_area_tenant_fk",
        "tenant_memberships_auth_user_fk",
        "tenant_areas_parent_area_id_fkey",
        "tenant_memberships_area_id_fkey",
        "tenant_user_groups_group_id_fkey",
    }
)


class TenantRelationConflict(APIException):
    status_code = 409
    default_detail = "La relación no es válida o cambió. Revisa y recarga los datos antes de volver a guardar."
    default_code = "tenant_relation_conflict"


def is_relation_conflict(error):
    cause = error.__cause__
    state = getattr(cause, "sqlstate", None)
    # A topology writer can lose serialization, deadlock resolution, or the
    # bounded tenant lock. Reload explicitly: replaying mutations is unsafe.
    if isinstance(error, OperationalError) and state in {"40001", "40P01", "55P03"}:
        return True
    constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
    return isinstance(error, IntegrityError) and (
        (state == "23503" and constraint in RELATION_CONSTRAINTS)
        or (
            state == "23514"
            and constraint
            in {
                "tenant_areas_acyclic",
                "tenant_areas_identity_immutable",
                "tenant_memberships_auth_user_check",
            }
        )
    )


def relation_conflict_schema(serializer):
    from drf_spectacular.utils import (
        OpenApiParameter,
        OpenApiResponse,
        extend_schema,
        extend_schema_view,
    )

    conflict = OpenApiResponse(
        description="Relación inválida o modificada; revisar y recargar antes de reintentar."
    )
    identifier = [OpenApiParameter("id", str, OpenApiParameter.PATH)]
    return extend_schema_view(
        retrieve=extend_schema(parameters=identifier),
        create=extend_schema(responses={201: serializer, 409: conflict}),
        update=extend_schema(
            parameters=identifier, responses={200: serializer, 409: conflict}
        ),
        partial_update=extend_schema(
            parameters=identifier, responses={200: serializer, 409: conflict}
        ),
        destroy=extend_schema(
            parameters=identifier, responses={204: None, 409: conflict}
        ),
    )
