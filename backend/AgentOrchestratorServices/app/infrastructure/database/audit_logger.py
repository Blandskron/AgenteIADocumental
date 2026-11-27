"""Append-only audit logger writing sanitized agent.* events to public.audit_logs (AG-009)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.application.tools.registry import redact_secrets
from sqlalchemy import text
from sqlalchemy.orm import Session


def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Redacts secrets and strips raw tokens or private document text from audit payloads."""
    sanitized: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        lowered = key.lower()
        if any(bad in lowered for bad in ("token", "secret", "password", "api_key", "raw_text", "chunk_content")):
            continue
        if isinstance(value, str):
            sanitized[key] = redact_secrets(value)[:250]
        elif isinstance(value, (int, float, bool)) or value is None:
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = [redact_secrets(str(item))[:120] for item in value[:20]]
        elif isinstance(value, dict):
            sanitized[key] = sanitize_audit_metadata(value)
    return sanitized


class AuditLogger:
    """Persists agent.run.*, agent.approval.* and agent.code_mode.* events into public.audit_logs."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session
        self.events: list[dict[str, Any]] = []

    def record(
        self,
        *,
        event_type: str,
        tenant_id: str,
        actor_user_id: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_meta = sanitize_audit_metadata({**(metadata or {}), "run_id": run_id})
        event = {
            "audit_id": str(uuid.uuid4()),
            "event_type": event_type,
            "tenant_id": tenant_id,
            "actor_user_id": actor_user_id,
            "run_id": run_id,
            "metadata": safe_meta,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(event)
        if self._session is not None:
            try:
                self._session.execute(
                    text(
                        """
                        INSERT INTO public.audit_logs (
                            audit_id, tenant_id, actor_user_id, action, resource_type, resource_id, metadata, created_at
                        ) VALUES (
                            :audit_id, :tenant_id, :actor_user_id, :action, 'agent_run', :resource_id, CAST(:metadata AS jsonb), NOW()
                        )
                        """
                    ),
                    {
                        "audit_id": event["audit_id"],
                        "tenant_id": tenant_id,
                        "actor_user_id": actor_user_id,
                        "action": event_type,
                        "resource_id": run_id,
                        "metadata": json.dumps(safe_meta),
                    },
                )
                self._session.commit()
            except Exception:
                self._session.rollback()
        return event

    def list_for_run(self, *, run_id: str, tenant_id: str) -> list[dict[str, Any]]:
        """Returns sanitized audit events for a specific run scoped strictly to tenant_id."""
        if self._session is not None:
            try:
                rows = self._session.execute(
                    text(
                        """
                        SELECT audit_id, action, actor_user_id, metadata, created_at
                        FROM public.audit_logs
                        WHERE tenant_id = :tenant_id
                          AND resource_type = 'agent_run'
                          AND resource_id = :run_id
                        ORDER BY created_at ASC
                        LIMIT 100
                        """
                    ),
                    {"tenant_id": tenant_id, "run_id": run_id},
                ).mappings().all()
                return [
                    {
                        "audit_id": str(r["audit_id"]),
                        "event_type": str(r["action"]),
                        "actor_user_id": str(r["actor_user_id"]),
                        "metadata": r["metadata"] if isinstance(r["metadata"], dict) else {},
                        "created_at": str(r["created_at"]),
                    }
                    for r in rows
                ]
            except Exception:
                pass
        return [
            dict(ev)
            for ev in self.events
            if ev["run_id"] == run_id and ev["tenant_id"] == tenant_id
        ]
