"""Runs and approvals repository with strict (tenant_id, owner_user_id) isolation (AG-008 / AG-009)."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class ApprovalConflictError(RuntimeError):
    """Raised when attempting to decide an approval that is already decided or invalid."""


class InMemoryRunsRepository:
    """In-memory repository mirroring agents.agent_runs and agents.agent_approvals constraints."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._approvals: dict[str, dict[str, Any]] = {}

    def find_by_idempotency(self, tenant_id: str, idempotency_key: str) -> dict[str, Any] | None:
        run_id = self._idempotency.get((tenant_id, idempotency_key))
        if not run_id:
            return None
        return deepcopy(self._runs.get(run_id))

    def create_run(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        idempotency_key: str,
        mode: str,
        goal: str,
        document_ids: list[str],
        provider: str | None = None,
    ) -> dict[str, Any]:
        existing = self.find_by_idempotency(tenant_id, idempotency_key)
        if existing is not None:
            return existing
        now = datetime.now(timezone.utc).isoformat()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        thread_id = f"thr_{uuid.uuid4().hex[:12]}"
        record: dict[str, Any] = {
            "run_id": run_id,
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "owner_user_id": owner_user_id,
            "idempotency_key": idempotency_key,
            "mode": mode,
            "goal": goal,
            "document_ids": list(document_ids),
            "status": "PENDING",
            "current_step": "queued",
            "steps": [],
            "sources": [],
            "code_executions": [],
            "result_markdown": None,
            "pending_approval": None,
            "studio_handoff": None,
            "error_code": None,
            "error_message": None,
            "provider": provider,
            "steps_used": 0,
            "usage_tokens": 0,
            "cancel_requested": False,
            "created_at": now,
            "updated_at": now,
        }
        self._runs[run_id] = record
        self._idempotency[(tenant_id, idempotency_key)] = run_id
        return deepcopy(record)

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        rec = self._runs[run_id]
        for key, value in fields.items():
            rec[key] = deepcopy(value)
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()
        return deepcopy(rec)

    def get_run(self, run_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any] | None:
        rec = self._runs.get(run_id)
        if not rec or rec["tenant_id"] != tenant_id or rec["owner_user_id"] != owner_user_id:
            return None
        return deepcopy(rec)

    def list_runs(self, *, tenant_id: str, owner_user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        matched = [
            deepcopy(rec)
            for rec in self._runs.values()
            if rec["tenant_id"] == tenant_id and rec["owner_user_id"] == owner_user_id
        ]
        matched.sort(key=lambda item: item["created_at"], reverse=True)
        return matched[: max(1, min(limit, 50))]

    def request_cancel(self, run_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any] | None:
        rec = self._runs.get(run_id)
        if not rec or rec["tenant_id"] != tenant_id or rec["owner_user_id"] != owner_user_id:
            return None
        rec["cancel_requested"] = True
        if rec["status"] in {"PENDING", "RUNNING", "WAITING_APPROVAL"}:
            rec["status"] = "CANCELLED"
            rec["current_step"] = "cancelled"
            rec["pending_approval"] = None
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()
        return deepcopy(rec)

    def is_cancel_requested(self, run_id: str) -> bool:
        rec = self._runs.get(run_id)
        return bool(rec and rec.get("cancel_requested"))

    def create_approval(
        self,
        *,
        run_id: str,
        tenant_id: str,
        requested_by_user_id: str,
        action: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        approval_id = f"apr_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        rec = {
            "approval_id": approval_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "requested_by_user_id": requested_by_user_id,
            "action": action,
            "summary": summary,
            "payload": deepcopy(payload or {}),
            "decision": "PENDING",
            "decided_by_user_id": None,
            "comment": None,
            "created_at": now,
            "decided_at": None,
        }
        self._approvals[approval_id] = rec
        return deepcopy(rec)

    def decide_approval(
        self,
        *,
        run_id: str,
        approval_id: str,
        tenant_id: str,
        owner_user_id: str,
        decision: str,
        comment: str = "",
    ) -> dict[str, Any]:
        run = self._runs.get(run_id)
        if not run or run["tenant_id"] != tenant_id or run["owner_user_id"] != owner_user_id:
            raise KeyError("Run not found for this tenant/user.")
        approval = self._approvals.get(approval_id)
        if not approval or approval["run_id"] != run_id or approval["tenant_id"] != tenant_id:
            raise KeyError("Approval not found for this run.")
        if approval["decision"] != "PENDING":
            raise ApprovalConflictError(f"Approval '{approval_id}' was already decided as {approval['decision']}.")
        normalized = "APPROVED" if decision.strip().lower() == "approve" else "REJECTED"
        approval["decision"] = normalized
        approval["decided_by_user_id"] = owner_user_id
        approval["comment"] = comment
        approval["decided_at"] = datetime.now(timezone.utc).isoformat()
        return deepcopy(approval)


class PostgresRunsRepository:
    """PostgreSQL implementation over agents.agent_runs and agents.agent_approvals with FOR UPDATE locking."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_idempotency(self, tenant_id: str, idempotency_key: str) -> dict[str, Any] | None:
        row = self._session.execute(
            text(
                """
                SELECT * FROM agents.agent_runs
                WHERE tenant_id = :tenant_id AND idempotency_key = :idempotency_key
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "idempotency_key": idempotency_key},
        ).mappings().first()
        return dict(row) if row else None

    def create_run(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        idempotency_key: str,
        mode: str,
        goal: str,
        document_ids: list[str],
        provider: str | None = None,
    ) -> dict[str, Any]:
        existing = self.find_by_idempotency(tenant_id, idempotency_key)
        if existing is not None:
            return existing
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        thread_id = f"thr_{uuid.uuid4().hex[:12]}"
        self._session.execute(
            text(
                """
                INSERT INTO agents.agent_runs (
                    run_id, thread_id, tenant_id, owner_user_id, idempotency_key,
                    mode, goal, document_ids, status, current_step, provider
                ) VALUES (
                    :run_id, :thread_id, :tenant_id, :owner_user_id, :idempotency_key,
                    :mode, :goal, CAST(:document_ids AS jsonb), 'PENDING', 'queued', :provider
                )
                """
            ),
            {
                "run_id": run_id,
                "thread_id": thread_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "idempotency_key": idempotency_key,
                "mode": mode,
                "goal": goal,
                "document_ids": json.dumps(document_ids),
                "provider": provider,
            },
        )
        self._session.commit()
        return self.get_run(run_id, tenant_id=tenant_id, owner_user_id=owner_user_id) or {}

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        allowed = {
            "status",
            "current_step",
            "steps",
            "sources",
            "result_markdown",
            "error_code",
            "error_message",
            "provider",
            "steps_used",
            "usage_tokens",
            "cancel_requested",
        }
        assignments = ["updated_at = NOW()"]
        params: dict[str, Any] = {"run_id": run_id}
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in {"steps", "sources"}:
                assignments.append(f"{key} = CAST(:{key} AS jsonb)")
                params[key] = json.dumps(value)
            else:
                assignments.append(f"{key} = :{key}")
                params[key] = value
        self._session.execute(
            text(f"UPDATE agents.agent_runs SET {', '.join(assignments)} WHERE run_id = :run_id"),
            params,
        )
        self._session.commit()
        row = self._session.execute(
            text("SELECT * FROM agents.agent_runs WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).mappings().first()
        return dict(row) if row else {}

    def get_run(self, run_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any] | None:
        row = self._session.execute(
            text(
                """
                SELECT * FROM agents.agent_runs
                WHERE run_id = :run_id AND tenant_id = :tenant_id AND owner_user_id = :owner_user_id
                """
            ),
            {"run_id": run_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id},
        ).mappings().first()
        return dict(row) if row else None

    def list_runs(self, *, tenant_id: str, owner_user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text(
                """
                SELECT * FROM agents.agent_runs
                WHERE tenant_id = :tenant_id AND owner_user_id = :owner_user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": tenant_id, "owner_user_id": owner_user_id, "limit": max(1, min(limit, 50))},
        ).mappings().all()
        return [dict(r) for r in rows]

    def request_cancel(self, run_id: str, *, tenant_id: str, owner_user_id: str) -> dict[str, Any] | None:
        self._session.execute(
            text(
                """
                UPDATE agents.agent_runs
                SET cancel_requested = TRUE,
                    status = CASE WHEN status IN ('PENDING', 'RUNNING', 'WAITING_APPROVAL') THEN 'CANCELLED' ELSE status END,
                    current_step = CASE WHEN status IN ('PENDING', 'RUNNING', 'WAITING_APPROVAL') THEN 'cancelled' ELSE current_step END,
                    updated_at = NOW()
                WHERE run_id = :run_id AND tenant_id = :tenant_id AND owner_user_id = :owner_user_id
                """
            ),
            {"run_id": run_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id},
        )
        self._session.commit()
        return self.get_run(run_id, tenant_id=tenant_id, owner_user_id=owner_user_id)

    def is_cancel_requested(self, run_id: str) -> bool:
        val = self._session.execute(
            text("SELECT cancel_requested FROM agents.agent_runs WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).scalar()
        return bool(val)

    def create_approval(
        self,
        *,
        run_id: str,
        tenant_id: str,
        requested_by_user_id: str,
        action: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        approval_id = f"apr_{uuid.uuid4().hex[:10]}"
        self._session.execute(
            text(
                """
                INSERT INTO agents.agent_approvals (
                    approval_id, run_id, tenant_id, requested_by_user_id, action, summary, payload, decision
                ) VALUES (
                    :approval_id, :run_id, :tenant_id, :user_id, :action, :summary, CAST(:payload AS jsonb), 'PENDING'
                )
                """
            ),
            {
                "approval_id": approval_id,
                "run_id": run_id,
                "tenant_id": tenant_id,
                "user_id": requested_by_user_id,
                "action": action,
                "summary": summary,
                "payload": json.dumps(payload or {}),
            },
        )
        self._session.commit()
        return {
            "approval_id": approval_id,
            "run_id": run_id,
            "tenant_id": tenant_id,
            "requested_by_user_id": requested_by_user_id,
            "action": action,
            "summary": summary,
            "payload": payload or {},
            "decision": "PENDING",
        }

    def decide_approval(
        self,
        *,
        run_id: str,
        approval_id: str,
        tenant_id: str,
        owner_user_id: str,
        decision: str,
        comment: str = "",
    ) -> dict[str, Any]:
        locked_run = self._session.execute(
            text(
                """
                SELECT run_id FROM agents.agent_runs
                WHERE run_id = :run_id AND tenant_id = :tenant_id AND owner_user_id = :owner_user_id
                FOR UPDATE
                """
            ),
            {"run_id": run_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id},
        ).first()
        if not locked_run:
            raise KeyError("Run not found for this tenant/user.")

        approval = self._session.execute(
            text(
                """
                SELECT approval_id, decision, action, summary, payload
                FROM agents.agent_approvals
                WHERE approval_id = :approval_id AND run_id = :run_id AND tenant_id = :tenant_id
                FOR UPDATE
                """
            ),
            {"approval_id": approval_id, "run_id": run_id, "tenant_id": tenant_id},
        ).mappings().first()
        if not approval:
            raise KeyError("Approval not found for this run.")
        if approval["decision"] != "PENDING":
            raise ApprovalConflictError(f"Approval '{approval_id}' was already decided as {approval['decision']}.")

        normalized = "APPROVED" if decision.strip().lower() == "approve" else "REJECTED"
        self._session.execute(
            text(
                """
                UPDATE agents.agent_approvals
                SET decision = :decision, decided_by_user_id = :user_id, comment = :comment, decided_at = NOW()
                WHERE approval_id = :approval_id
                """
            ),
            {
                "decision": normalized,
                "user_id": owner_user_id,
                "comment": comment,
                "approval_id": approval_id,
            },
        )
        self._session.commit()
        return {
            "approval_id": approval_id,
            "run_id": run_id,
            "decision": normalized,
            "action": approval["action"],
            "summary": approval["summary"],
            "comment": comment,
        }
