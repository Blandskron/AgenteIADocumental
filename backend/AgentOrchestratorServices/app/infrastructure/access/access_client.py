"""Read-only HTTP client for DocumentAccessServices with JWT propagation (AG-025)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote
import urllib.request

from app.application.tools.registry import (
    ToolPolicy,
    ToolRegistry,
    ToolSpec,
    redact_secrets,
)


class DocumentAccessHttpClient:
    """Fetches authorized document metadata from DocumentAccessServices propagating the user JWT."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        transport: Any | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def get_document_metadata(self, *, document_id: str, user_jwt: str) -> dict[str, Any]:
        if not user_jwt or not user_jwt.strip():
            raise PermissionError("Missing user JWT for DocumentAccessServices propagation.")
        safe_id = quote(document_id.strip(), safe="")
        url = f"{self._base_url}/api/v1/documents/{safe_id}/metadata"
        headers = {
            "Authorization": f"Bearer {user_jwt.strip()}",
            "Accept": "application/json",
        }
        if self._transport is not None:
            raw = self._transport(url, headers, self._timeout)
        else:
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                raise RuntimeError(redact_secrets(f"DocumentAccessServices call failed: {exc}")) from None

        if not isinstance(raw, dict):
            return {"document_id": document_id, "metadata": {}}
        return {
            "document_id": str(raw.get("document_id") or document_id),
            "filename": str(raw.get("filename") or ""),
            "status": str(raw.get("status") or ""),
            "mime_type": str(raw.get("mime_type") or raw.get("content_type") or ""),
            "owner_user_id": str(raw.get("owner_user_id") or ""),
            "updated_at": str(raw.get("updated_at") or ""),
        }


def register_document_access_tools(
    registry: ToolRegistry,
    access_client: DocumentAccessHttpClient,
) -> None:
    """Registers strictly read-only document metadata inspection in ToolRegistry."""

    def _handler(args: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        return access_client.get_document_metadata(
            document_id=str(args.get("document_id") or ""),
            user_jwt=str(user.get("raw_token") or ""),
        )

    registry.register(
        ToolSpec(
            name="get_document_metadata",
            description="Consulta metadatos autorizados de un documento específico (solo lectura).",
            input_schema={
                "type": "object",
                "properties": {"document_id": {"type": "string"}},
                "required": ["document_id"],
            },
            policy=ToolPolicy(read_only=True, requires_human_approval=False, max_results=1),
            handler=_handler,
        )
    )
