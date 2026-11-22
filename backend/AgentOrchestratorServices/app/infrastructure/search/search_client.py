"""Read-only HTTP client for DocumentSearchServices with JWT propagation (AG-015)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
import urllib.request

from app.application.tools.registry import (
    ToolPolicy,
    ToolRegistry,
    ToolSpec,
    redact_secrets,
)


class DocumentSearchHttpClient:
    """Queries DocumentSearchServices GET /api/v1/documents/search propagating the user's JWT."""

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

    def search(
        self,
        *,
        query: str,
        user_jwt: str,
        limit: int = 10,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        if not user_jwt or not user_jwt.strip():
            raise PermissionError("Missing user JWT for DocumentSearchServices propagation.")
        safe_limit = max(1, min(int(limit), 20))
        params: dict[str, str] = {"q": (query or "").strip(), "limit": str(safe_limit)}
        if status_filter:
            params["status"] = status_filter.strip()
        url = f"{self._base_url}/api/v1/documents/search?{urlencode(params)}"
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
                raise RuntimeError(redact_secrets(f"DocumentSearchServices call failed: {exc}")) from None

        if not isinstance(raw, dict):
            return {"items": [], "total": 0}

        items = raw.get("items") or raw.get("documents") or []
        normalized = []
        for item in items[:safe_limit]:
            if isinstance(item, dict) and (item.get("document_id") or item.get("id")):
                normalized.append(
                    {
                        "document_id": str(item.get("document_id") or item.get("id")),
                        "filename": str(item.get("filename") or ""),
                        "status": str(item.get("status") or ""),
                        "snippet": str(item.get("snippet") or item.get("excerpt") or "")[:300],
                    }
                )
        return {"items": normalized, "total": int(raw.get("total", len(normalized)))}


def register_document_search_tools(
    registry: ToolRegistry,
    search_client: DocumentSearchHttpClient,
) -> None:
    """Registers hybrid FTS/trigram discovery from DocumentSearchServices in ToolRegistry."""

    def _handler(args: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        return search_client.search(
            query=str(args.get("query") or ""),
            user_jwt=str(user.get("raw_token") or ""),
            limit=int(args.get("limit") or 10),
            status_filter=args.get("status"),
        )

    registry.register(
        ToolSpec(
            name="search_documents_fts",
            description="Busca documentos autorizados vía DocumentSearchServices (FTS + trigram).",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "status": {"type": "string"},
                },
                "required": ["query"],
            },
            policy=ToolPolicy(read_only=True, requires_human_approval=False, max_results=20),
            handler=_handler,
        )
    )
