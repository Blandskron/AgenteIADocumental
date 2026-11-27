"""LLM client for KnowledgeStudioServices supporting Ollama local, Groq, and OpenAI-compatible endpoints (EVO-009)."""

from __future__ import annotations

import json
import os
import re
from typing import Any
import urllib.request

from app.application.studio_runner import StudioJobRequest


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("LLM returned empty response for Studio artifact.")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Parsed Studio artifact payload is not a JSON object.")
    return parsed


def _build_deterministic_grounded_fallback(
    request: StudioJobRequest,
    chunks: dict[tuple[str, int], str],
) -> dict[str, Any]:
    """Produces a strictly grounded artifact from real chunk quotes when no external LLM is configured."""
    claims: list[dict[str, Any]] = []
    body_lines: list[str] = []
    for idx, ((doc_id, chunk_index), chunk_text) in enumerate(list(chunks.items())[:8], start=1):
        snippet = " ".join((chunk_text or "").split())[:220].strip()
        if len(snippet) < 3:
            continue
        claims.append(
            {
                "statement": snippet,
                "citations": [
                    {
                        "document_id": doc_id,
                        "chunk_index": chunk_index,
                        "quote_text": snippet[:180],
                    }
                ],
            }
        )
        body_lines.append(f"- {snippet} [Fuente {idx}]")

    title = str(request.options.get("title") or f"Artefacto {request.template_id}")[:200]
    payload: dict[str, Any] = {
        "template_id": request.template_id,
        "template_version": "1.0.0",
        "title": title,
        "body_md": "\n".join(body_lines) or "Sin fragmentos disponibles.",
        "claims": claims,
    }
    if request.template_id == "evidence_table" and claims:
        payload["table_columns"] = ["Fuente", "Evidencia"]
        payload["table_rows"] = [
            {
                "cells": {"Fuente": f"{c['citations'][0]['document_id']}#{c['citations'][0]['chunk_index']}", "Evidencia": c["statement"]},
                "citations": c["citations"],
                "verified": True,
            }
            for c in claims
        ]
    elif request.template_id == "proposed_tasks" and claims:
        payload["tasks"] = [
            {
                "title": f"Revisar evidencia: {c['statement'][:120]}",
                "status": "proposed",
                "citations": c["citations"],
            }
            for c in claims[:5]
        ]
    return payload


class StudioLlmClient:
    """Generates strictly cited ArtifactContent JSON via Ollama/Groq/OpenAI-compatible HTTP API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 45.0,
        transport: Any | None = None,
    ) -> None:
        self._base_url = (base_url or "").strip().rstrip("/")
        self._api_key = (api_key or "").strip()
        self._timeout = timeout_seconds
        self._transport = transport

    def _resolve_endpoint(self, model_id: str) -> tuple[str, str, str]:
        if self._base_url:
            return f"{self._base_url}/chat/completions", self._api_key, model_id
        groq_key = (os.environ.get("GROQ_API_KEY") or "").strip()
        if groq_key:
            return "https://api.groq.com/openai/v1/chat/completions", groq_key, model_id or "llama-3.3-70b-versatile"
        ollama_url = (os.environ.get("OLLAMA_BASE_URL") or "").strip().rstrip("/")
        if ollama_url:
            return f"{ollama_url}/v1/chat/completions", "ollama", model_id or "qwen2.5:3b"
        return "", "", model_id

    def generate_artifact_json(
        self,
        request: StudioJobRequest,
        chunks: dict[tuple[str, int], str],
        repair_errors: list[str] | None = None,
    ) -> dict[str, Any]:
        endpoint, api_key, model = self._resolve_endpoint(request.model_id)
        if not endpoint:
            return _build_deterministic_grounded_fallback(request, chunks)

        context_lines = [
            f"[{doc_id}#{chunk_idx}] {(text or '')[:1200]}"
            for (doc_id, chunk_idx), text in list(chunks.items())[:16]
        ]
        repair_hint = (
            f"\nErrores previos a corregir obligatoriamente: {'; '.join(repair_errors)}"
            if repair_errors
            else ""
        )
        system_prompt = (
            "Eres el motor de Knowledge Studio de Blandskron Documental. "
            "Responde EXCLUSIVAMENTE con un objeto JSON válido compatible con ArtifactContent: "
            '{"template_id": "...", "title": "...", "body_md": "...", "claims": [{"statement": "...", '
            '"citations": [{"document_id": "...", "chunk_index": 0, "quote_text": "cita literal exacta"}]}]}. '
            "Cada quote_text DEBE aparecer literalmente dentro del fragmento citado."
        )
        user_prompt = (
            f"Plantilla: {request.template_id}\n"
            f"Fragmentos autorizados:\n" + "\n\n".join(context_lines) + repair_hint
        )
        body = {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if self._transport is not None:
            raw_resp = self._transport(endpoint, body, headers, self._timeout)
        else:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw_resp = json.loads(resp.read().decode("utf-8"))

        choices = raw_resp.get("choices") or []
        content = ((choices[0] if choices else {}).get("message") or {}).get("content") or ""
        return _extract_json_object(str(content))
