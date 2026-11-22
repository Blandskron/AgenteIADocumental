"""Strict checkpointing over agents.agent_checkpoints with LANGGRAPH_STRICT_MSGPACK=true (AG-008)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from app.application.tools.registry import redact_secrets
from sqlalchemy import text
from sqlalchemy.orm import Session

MAX_CHECKPOINT_QUOTE_CHARS = 400
MAX_CHECKPOINT_EVIDENCE_ITEMS = 40


class UnsafeSerializationError(ValueError):
    """Raised when a checkpoint attempts to serialize non-primitive / unsafe Python objects."""


def is_strict_msgpack_enabled() -> bool:
    return os.environ.get("LANGGRAPH_STRICT_MSGPACK", "true").strip().lower() not in {"0", "false", "no"}


def _validate_strict_primitive(value: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        raise UnsafeSerializationError("Checkpoint state exceeds maximum nesting depth.")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, list):
        return [_validate_strict_primitive(item, depth=depth + 1) for item in value]
    if isinstance(value, tuple):
        return [_validate_strict_primitive(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise UnsafeSerializationError("Checkpoint dictionary keys must be strings.")
            sanitized[key] = _validate_strict_primitive(item, depth=depth + 1)
        return sanitized
    raise UnsafeSerializationError(
        f"Type '{type(value).__name__}' is disallowed under LANGGRAPH_STRICT_MSGPACK=true."
    )


def compact_checkpoint_state(state: dict[str, Any]) -> dict[str, Any]:
    """Bounds evidence snippets so checkpoints store compact document_id#chunk_index references, never full docs."""
    sanitized = _validate_strict_primitive(state)
    evidence = sanitized.get("evidence")
    if isinstance(evidence, list):
        compact_evidence = []
        for item in evidence[:MAX_CHECKPOINT_EVIDENCE_ITEMS]:
            if isinstance(item, dict):
                compact_evidence.append(
                    {
                        "document_id": str(item.get("document_id") or ""),
                        "chunk_index": int(item.get("chunk_index") or 0),
                        "filename": str(item.get("filename") or ""),
                        "quote": str(item.get("quote") or "")[:MAX_CHECKPOINT_QUOTE_CHARS],
                    }
                )
        sanitized["evidence"] = compact_evidence
    return sanitized


@dataclass(frozen=True)
class CheckpointRecord:
    thread_id: str
    checkpoint_seq: int
    tenant_id: str
    owner_user_id: str
    node_name: str
    state: dict[str, Any]


class InMemoryCheckpointer:
    """In-memory checkpointer with identical strict serialization & tenant isolation semantics for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, list[CheckpointRecord]] = {}

    def save(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
        node_name: str,
        state: dict[str, Any],
    ) -> CheckpointRecord:
        if not is_strict_msgpack_enabled():
            raise UnsafeSerializationError("LANGGRAPH_STRICT_MSGPACK must remain enabled.")
        compact = compact_checkpoint_state(state)
        entries = self._store.setdefault(thread_id, [])
        seq = len(entries) + 1
        rec = CheckpointRecord(
            thread_id=thread_id,
            checkpoint_seq=seq,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            node_name=node_name,
            state=json.loads(json.dumps(compact)),
        )
        entries.append(rec)
        return rec

    def load_latest(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
    ) -> CheckpointRecord | None:
        entries = self._store.get(thread_id) or []
        for rec in reversed(entries):
            if rec.tenant_id == tenant_id and rec.owner_user_id == owner_user_id:
                return CheckpointRecord(
                    thread_id=rec.thread_id,
                    checkpoint_seq=rec.checkpoint_seq,
                    tenant_id=rec.tenant_id,
                    owner_user_id=rec.owner_user_id,
                    node_name=rec.node_name,
                    state=json.loads(json.dumps(rec.state)),
                )
        return None

    def list_metadata(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
    ) -> list[dict[str, Any]]:
        entries = self._store.get(thread_id) or []
        return [
            {
                "thread_id": rec.thread_id,
                "checkpoint_seq": rec.checkpoint_seq,
                "node_name": rec.node_name,
            }
            for rec in entries
            if rec.tenant_id == tenant_id and rec.owner_user_id == owner_user_id
        ]

    def prune_old_checkpoints(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
        keep_last: int = 5,
    ) -> int:
        keep = max(1, int(keep_last))
        entries = self._store.get(thread_id) or []
        owned = [r for r in entries if r.tenant_id == tenant_id and r.owner_user_id == owner_user_id]
        if len(owned) <= keep:
            return 0
        to_drop = {r.checkpoint_seq for r in owned[:-keep]}
        before = len(entries)
        self._store[thread_id] = [
            r
            for r in entries
            if not (
                r.tenant_id == tenant_id
                and r.owner_user_id == owner_user_id
                and r.checkpoint_seq in to_drop
            )
        ]
        return before - len(self._store[thread_id])


class PostgresAgentCheckpointer:
    """PostgreSQL checkpointer writing strictly serialized states into agents.agent_checkpoints."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
        node_name: str,
        state: dict[str, Any],
    ) -> CheckpointRecord:
        if not is_strict_msgpack_enabled():
            raise UnsafeSerializationError("LANGGRAPH_STRICT_MSGPACK must remain enabled.")
        compact = compact_checkpoint_state(state)
        row = self._session.execute(
            text(
                """
                SELECT COALESCE(MAX(checkpoint_seq), 0) + 1
                FROM agents.agent_checkpoints
                WHERE thread_id = :thread_id
                """
            ),
            {"thread_id": thread_id},
        ).scalar_one()
        seq = int(row)
        self._session.execute(
            text(
                """
                INSERT INTO agents.agent_checkpoints (
                    thread_id, checkpoint_seq, tenant_id, owner_user_id, node_name, state_format, state_payload
                ) VALUES (
                    :thread_id, :seq, :tenant_id, :owner_user_id, :node_name, 'strict_json', CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "thread_id": thread_id,
                "seq": seq,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "node_name": node_name,
                "payload": json.dumps(compact),
            },
        )
        self._session.commit()
        return CheckpointRecord(
            thread_id=thread_id,
            checkpoint_seq=seq,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            node_name=node_name,
            state=compact,
        )

    def load_latest(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
    ) -> CheckpointRecord | None:
        row = self._session.execute(
            text(
                """
                SELECT thread_id, checkpoint_seq, tenant_id, owner_user_id, node_name, state_payload
                FROM agents.agent_checkpoints
                WHERE thread_id = :thread_id
                  AND tenant_id = :tenant_id
                  AND owner_user_id = :owner_user_id
                ORDER BY checkpoint_seq DESC
                LIMIT 1
                """
            ),
            {"thread_id": thread_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id},
        ).mappings().first()
        if not row:
            return None
        payload = row["state_payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return CheckpointRecord(
            thread_id=str(row["thread_id"]),
            checkpoint_seq=int(row["checkpoint_seq"]),
            tenant_id=str(row["tenant_id"]),
            owner_user_id=str(row["owner_user_id"]),
            node_name=str(row["node_name"]),
            state=dict(payload or {}),
        )

    def list_metadata(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text(
                """
                SELECT thread_id, checkpoint_seq, node_name, created_at
                FROM agents.agent_checkpoints
                WHERE thread_id = :thread_id
                  AND tenant_id = :tenant_id
                  AND owner_user_id = :owner_user_id
                ORDER BY checkpoint_seq ASC
                """
            ),
            {"thread_id": thread_id, "tenant_id": tenant_id, "owner_user_id": owner_user_id},
        ).mappings().all()
        return [
            {
                "thread_id": str(r["thread_id"]),
                "checkpoint_seq": int(r["checkpoint_seq"]),
                "node_name": str(r["node_name"]),
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]

    def prune_old_checkpoints(
        self,
        *,
        thread_id: str,
        tenant_id: str,
        owner_user_id: str,
        keep_last: int = 5,
    ) -> int:
        keep = max(1, int(keep_last))
        result = self._session.execute(
            text(
                """
                DELETE FROM agents.agent_checkpoints
                WHERE thread_id = :thread_id
                  AND tenant_id = :tenant_id
                  AND owner_user_id = :owner_user_id
                  AND checkpoint_seq NOT IN (
                      SELECT checkpoint_seq
                      FROM agents.agent_checkpoints
                      WHERE thread_id = :thread_id
                        AND tenant_id = :tenant_id
                        AND owner_user_id = :owner_user_id
                      ORDER BY checkpoint_seq DESC
                      LIMIT :keep_last
                  )
                """
            ),
            {
                "thread_id": thread_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_user_id,
                "keep_last": keep,
            },
        )
        self._session.commit()
        return int(result.rowcount or 0)
