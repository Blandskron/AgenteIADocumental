"""Knowledge Studio & DocumentExportServices handoff adapter for human-approved agent outputs (AG-012)."""

from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.request
from typing import Any

from app.application.tools.registry import redact_secrets


def validate_sources_groundedness(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Verifies every claim references an actually retrieved (document_id, chunk_index) pair."""
    valid_refs = {
        (str(item.get("document_id") or ""), int(item.get("chunk_index") or 0))
        for item in evidence
        if item.get("document_id")
    }
    errors: list[str] = []
    if not claims:
        return True, []
    for idx, claim in enumerate(claims, start=1):
        doc_id = str(claim.get("document_id") or "")
        chunk_idx = int(claim.get("chunk_index") or 0)
        if (doc_id, chunk_idx) not in valid_refs:
            errors.append(f"Claim #{idx} references unverified source {doc_id}#{chunk_idx}.")
    return len(errors) == 0, errors


def build_fallback_csv(sources: list[dict[str, Any]], result_markdown: str) -> str:
    """Produces a safe CSV export when Knowledge Studio is disabled or unreachable."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["source_index", "document_id", "chunk_index", "filename", "quote"])
    for idx, src in enumerate(sources, start=1):
        quote = str(src.get("quote") or "").replace("\n", " ").strip()
        # Prevent CSV formula injection (=, +, -, @)
        if quote and quote[0] in ("=", "+", "-", "@"):
            quote = "'" + quote
        writer.writerow([idx, src.get("document_id", ""), src.get("chunk_index", 0), src.get("filename", ""), quote])
    if not sources and result_markdown:
        writer.writerow([0, "", 0, "summary", result_markdown[:300].replace("\n", " ")])
    return buf.getvalue()


class StudioHandoffClient:
    """Persists human-approved reports/tables into KnowledgeStudioServices POST /api/v1/studio/artifacts."""

    def __init__(
        self,
        studio_base_url: str,
        *,
        export_base_url: str = "http://document-export-service:8000",
        timeout_seconds: float = 15.0,
        transport: Any | None = None,
    ) -> None:
        self._studio_base_url = studio_base_url.rstrip("/")
        self._export_base_url = export_base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def save_approved_artifact(
        self,
        *,
        user_jwt: str,
        title: str,
        template_id: str,
        result_markdown: str,
        sources: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not user_jwt or not user_jwt.strip():
            raise PermissionError("User JWT is required to save artifacts into Knowledge Studio.")

        claims = [
            {
                "text": str(src.get("quote") or "Evidencia documental"),
                "document_id": str(src.get("document_id") or ""),
                "chunk_index": int(src.get("chunk_index") or 0),
                "quote": str(src.get("quote") or ""),
            }
            for src in sources
            if src.get("document_id")
        ]
        grounded, errors = validate_sources_groundedness(claims, evidence)
        if not grounded:
            raise ValueError(f"Groundedness check failed: {'; '.join(errors)}")

        doc_ids = sorted({c["document_id"] for c in claims})
        if not doc_ids:
            raise ValueError("Cannot persist a Studio artifact without at least one verified document source.")

        payload = {
            "template_id": template_id,
            "title": title[:200],
            "document_ids": doc_ids,
            "content": {
                "summary": result_markdown[:4000],
                "sections": [
                    {
                        "heading": title[:120],
                        "body": result_markdown,
                        "citations": [
                            {
                                "document_id": c["document_id"],
                                "chunk_index": c["chunk_index"],
                                "quote": c["quote"][:240],
                            }
                            for c in claims
                        ],
                    }
                ],
                "claims": claims,
            },
        }
        url = f"{self._studio_base_url}/api/v1/studio/artifacts"
        headers = {
            "Authorization": f"Bearer {user_jwt.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
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
            # Clean degradation if --profile studio is not active or returns 503
            return {
                "status": "studio_unavailable_fallback",
                "reason": redact_secrets(str(exc)),
                "fallback_markdown": result_markdown,
                "fallback_csv": build_fallback_csv(sources, result_markdown),
            }

        artifact_id = str(response.get("artifact_id") or response.get("id") or "")
        return {
            "status": "saved",
            "artifact_id": artifact_id,
            "freshness_status": response.get("status") or "FRESH",
            "studio_url": f"/studio?artifact={artifact_id}" if artifact_id else "/studio",
            "export_pdf_endpoint": f"{self._export_base_url}/api/v1/exports/studio-artifact/{artifact_id}"
            if artifact_id
            else None,
            "grounded": True,
        }
