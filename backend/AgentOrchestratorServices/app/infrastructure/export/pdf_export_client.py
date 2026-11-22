"""HTTP adapter to export completed agent runs to PDF via DocumentExportServices (AG-029)."""

from __future__ import annotations

import json
from typing import Any
import urllib.request

from app.application.export_service import export_run_markdown
from app.application.tools.registry import redact_secrets


class AgentPdfExportClient:
    """Calls DocumentExportServices POST /api/v1/exports/chat-snapshot propagating user JWT."""

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

    def export_run_to_pdf(self, *, run: dict[str, Any], user_jwt: str) -> dict[str, Any]:
        if not user_jwt or not user_jwt.strip():
            raise PermissionError("Missing user JWT for DocumentExportServices.")

        run_id = str(run.get("run_id") or "")
        payload = {
            "title": str(run.get("goal") or f"Informe Agente {run_id}")[:180],
            "question": str(run.get("goal") or ""),
            "answer": str(run.get("result_markdown") or ""),
            "sources": run.get("sources") or [],
            "metadata": {
                "exported_from": "agent_orchestrator",
                "run_id": run_id,
                "provider": run.get("provider"),
                "steps_used": run.get("steps_used", 0),
            },
        }
        url = f"{self._base_url}/api/v1/exports/chat-snapshot"
        headers = {
            "Authorization": f"Bearer {user_jwt.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": f"agent-pdf-{run_id}",
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
