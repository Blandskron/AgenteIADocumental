"""Tests for EVO-016: optional reranker, multi-turn query rewrite, and shared E5 client."""

from __future__ import annotations

from app.domain.chat import ChatMessage, MessageRole
from app.domain.embeddings import SearchResult
from app.infrastructure.ai.optional_reranker import (
    OptionalCrossEncoderReranker,
    SharedEmbeddingHttpClient,
    rewrite_multiturn_query,
)


def test_reranker_is_noop_when_disabled_and_promotes_exact_match_when_enabled() -> None:
    c1 = SearchResult("d1", "c1", 0, "Texto generico sin terminos clave", 0.82, "a.pdf")
    c2 = SearchResult("d2", "c2", 0, "El plazo maximo de garantia legal es de 45 dias", 0.78, "b.pdf")

    disabled = OptionalCrossEncoderReranker(enabled=False)
    assert [c.chunk_id for c in disabled.rerank("plazo garantia legal", [c1, c2])] == ["c1", "c2"]

    enabled = OptionalCrossEncoderReranker(enabled=True)
    reranked = enabled.rerank("plazo garantia legal", [c1, c2])
    assert reranked[0].chunk_id == "c2"
    assert "reranker_score" in reranked[0].metadata


def test_rewrite_multiturn_query_expands_short_followup() -> None:
    history = [ChatMessage(role=MessageRole.USER, content="Que dice el contrato de arriendo sobre renovacion?")]
    expanded = rewrite_multiturn_query("Y el plazo?", history)
    assert "contrato de arriendo" in expanded

    long_q = "Cual es la penalizacion exacta por incumplimiento de SLA en el anexo tecnico vigente?"
    assert rewrite_multiturn_query(long_q, history) == long_q


def test_shared_embedding_http_client_parses_vector() -> None:
    client = SharedEmbeddingHttpClient(
        "http://rag-document-embedding-service:8000",
        transport=lambda _url, _payload, _t: {"embedding": [0.1, 0.2, 0.3]},
    )
    assert client.embed_query("consulta") == [0.1, 0.2, 0.3]
