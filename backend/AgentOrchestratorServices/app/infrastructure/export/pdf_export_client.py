"""HTTP adapter to export completed agent runs to PDF via DocumentExportServices (AG-029)."""

from __future__ import annotations

import json
from typing import Any
import urllib.request
import uuid

from app.application.export_service import export_run_markdown
from app.application.tools.registry import redact_secrets


class AgentPdfExportClient:
    """Calls DocumentExportServices POST /api/v1/exports/chat-message/pdf propagating user JWT."""

    def __init__(
        self,
        export_base_url: str = "http://document-export-service:8000",
        *,
        timeout_seconds: float = 15.0,
        transport: Any | None = None,
    ) -> None:
        self._base_url = export_base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    @staticmethod
    def _normalize_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for src in sources[:40]:
            if not isinstance(src, dict):
                continue
            item: dict[str, Any] = {
                "document_id": str(src.get("document_id") or "")[:128],
                "filename": str(src.get("filename") or "")[:256],
                "snippet": str(src.get("quote") or src.get("snippet") or src.get("content") or "")[:2000],
            }
            if src.get("chunk_id"):
                item["chunk_id"] = str(src["chunk_id"])[:128]
            if isinstance(src.get("score"), (int, float)):
                item["score"] = float(src["score"])
            normalized.append(item)
        return normalized

    def export_run_to_pdf(self, *, run: dict[str, Any], user_jwt: str) -> dict[str, Any]:
        if not user_jwt or not user_jwt.strip():
            raise PermissionError("Missing user JWT for DocumentExportServices.")

        run_id = str(run.get("run_id") or "")
        goal_text = str(run.get("goal") or "").strip()
        answer_text = str(run.get("result_markdown") or "").strip() or goal_text or f"Informe Agente {run_id}"
        payload = {
            "title": (goal_text or f"Informe Agente {run_id}")[:160],
            "question": goal_text[:8000],
            "answer": answer_text[:50000],
            "sources": self._normalize_sources(run.get("sources") or []),
            "metadata": {
                "exported_from": "agent_orchestrator",
                "run_id": run_id,
                "provider": run.get("provider"),
                "steps_used": int(run.get("steps_used") or 0),
            },
        }
        url = f"{self._base_url}/api/v1/exports/chat-message/pdf"
        idempotency_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"blandskron:agent-pdf:{run_id}"))
        headers = {
            "Authorization": f"Bearer {user_jwt.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": idempotency_uuid,
        }

        try:
            if self._transport is not None:
                response = self._transport(url, payload, headers, self._timeout)
            else:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    response = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {
                "status": "export_service_unavailable_fallback",
                "reason": redact_secrets(str(exc)),
                "fallback_markdown": export_run_markdown(run),
            }

        export_id = str(response.get("export_id") or response.get("id") or "")
        return {
            "status": "created",
            "export_id": export_id,
            "download_url": f"{self._base_url}/api/v1/exports/{export_id}/download" if export_id else None,
        }
