from sqlalchemy import false, or_, select, true
from sqlalchemy.sql.elements import ColumnElement

from app.config.security import is_superadmin_user, tenant_ids_for_role, user_groups
from app.infrastructure.database.models import document_assignments, documents


def document_access_filter(user: dict) -> ColumnElement[bool]:
    """Match DocumentLibrary access and ignore cancelled or expired grants."""
    if is_superadmin_user(user):
        return true()

    clauses = []
    metadata = documents.c.metadata
    admin_tenant_ids = tenant_ids_for_role(user, "TENANT_ADMIN")
    if admin_tenant_ids:
        clauses.extend((
            documents.c.tenant_id.in_(admin_tenant_ids),
            metadata["tenant_id"].astext.in_(admin_tenant_ids),
        ))

    user_id = str(user.get("user_id") or user.get("sub") or user.get("username") or "")
    if user_id:
        active_assignment = select(1).where(
            document_assignments.c.document_id == documents.c.document_id,
            document_assignments.c.status.not_in(("CANCELLED", "EXPIRED")),
            or_(
                document_assignments.c.assigned_to_user_id == user_id,
                document_assignments.c.assigned_by_user_id == user_id,
            ),
        ).exists()
        clauses.extend((
            documents.c.owner_user_id == user_id,
            metadata["owner_user_id"].astext == user_id,
            active_assignment,
        ))

    clauses.extend(metadata.contains({"owner_groups": [group]}) for group in user_groups(user))
    return or_(false(), *clauses)
