"""Optional local ONNX reranker, multi-turn query rewriter, and shared-E5 HTTP client (EVO-016)."""

from __future__ import annotations

from dataclasses import replace
import json
import os
import re
from typing import Any
import urllib.request

from app.domain.chat import ChatMessage, MessageRole
from app.domain.embeddings import SearchResult


def is_reranker_enabled() -> bool:
    return os.environ.get("RERANKER_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def is_query_rewrite_enabled() -> bool:
    return os.environ.get("QUERY_REWRITE_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9áéíóúñ]{3,}", (text or "").lower())}


def rewrite_multiturn_query(question: str, history: list[ChatMessage] | None = None) -> str:
    """Expands short follow-up questions using the immediately preceding user turn."""
    clean = (question or "").strip()
    if not clean or not history:
        return clean
    if len(clean.split()) >= 8:
        return clean
    previous_user = [m.content.strip() for m in history if m.role == MessageRole.USER and m.content.strip()]
    if not previous_user:
        return clean
    anchor = previous_user[-1][:200]
    return f"{clean} (contexto previo: {anchor})"


class OptionalCrossEncoderReranker:
    """Reranks top-K candidates when RERANKER_ENABLED=true; no-op when disabled."""

    def __init__(self, *, enabled: bool | None = None, onnx_model_path: str | None = None) -> None:
        self._enabled = is_reranker_enabled() if enabled is None else enabled
        self._onnx_model_path = (onnx_model_path or os.environ.get("RERANKER_ONNX_MODEL_PATH") or "").strip()

    def rerank(self, query: str, candidates: list[SearchResult], *, top_k: int | None = None) -> list[SearchResult]:
        if not self._enabled or len(candidates) <= 1:
            return candidates[:top_k] if top_k else candidates

        q_tokens = _tokenize(query)
        scored: list[tuple[float, SearchResult]] = []
        for item in candidates:
            c_tokens = _tokenize(item.content)
            overlap = (len(q_tokens & c_tokens) / max(1, len(q_tokens))) if q_tokens else 0.0
            combined = round(0.65 * float(item.score) + 0.35 * overlap, 6)
            enriched = replace(
                item,
                score=combined,
                metadata={**(item.metadata or {}), "reranker_score": combined},
            )
            scored.append((combined, enriched))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        ranked = [item for _, item in scored]
        return ranked[:top_k] if top_k else ranked


class SharedEmbeddingHttpClient:
    """Optional HTTP client to delegate E5 embeddings to RagDocumentEmbeddingServices (-600 MB RAM)."""

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

    def embed_query(self, text: str) -> list[float]:
        url = f"{self._base_url}/api/v1/internal/embed-query"
        payload = {"text": text}
        if self._transport is not None:
            resp = self._transport(url, payload, self._timeout)
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as handle:
                resp = json.loads(handle.read().decode("utf-8"))
        vector = resp.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise ValueError("Shared embedding service returned an invalid embedding vector.")
        return [float(v) for v in vector]
