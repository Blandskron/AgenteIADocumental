"""Tests for EVO-007 (page/section citations, insufficient-evidence gate) and EVO-010 (real SSE stream)."""

from __future__ import annotations

from collections.abc import Iterator

from app.application.chat.use_cases.ask_document_chat import INSUFFICIENT_EVIDENCE_ANSWER, AskDocumentChat
from app.domain.embeddings import SearchResult


class _FakeSearch:
    def __init__(self, results: list[SearchResult]) -> None:
        self._results = results

    def execute(self, _question: str, document_ids=None):
        return list(self._results)

    def get_document_context(self, document_ids, limit_per_document=16):
        return list(self._results)


class _SpyLLM:
    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas
        self.called = False

    def answer_with_context(self, question, context, history=None, mode="qa") -> str:
        self.called = True
        return "".join(self._deltas)

    def stream_answer_with_context(self, question, context, history=None, mode="qa") -> Iterator[str]:
        self.called = True
        yield from self._deltas


def test_insufficient_evidence_gate_skips_llm_when_no_chunks_found() -> None:
    llm = _SpyLLM(["No deberia llamarse"])
    uc = AskDocumentChat(_FakeSearch([]), llm)  # type: ignore[arg-type]

    answer = uc.execute("Cual es el monto?")
    assert answer.provider_status == "insufficient_evidence"
    assert answer.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert answer.sources == []
    assert llm.called is False


def test_citations_preserve_page_section_chunk_index_and_rrf_score() -> None:
    chunk = SearchResult(
        document_id="doc-1",
        chunk_id="chk-1",
        chunk_index=3,
        content="[page 7]\nEl plazo de renovacion es de 30 dias.",
        score=0.92,
        filename="contrato.pdf",
        metadata={"section": "Clausula 4", "rrf_score": 0.032787},
    )
    llm = _SpyLLM(["El plazo es de ", "30 dias [Fuente 1]."])
    uc = AskDocumentChat(_FakeSearch([chunk]), llm)  # type: ignore[arg-type]

    ans = uc.execute("Cual es el plazo?")
    assert len(ans.sources) == 1
    src = ans.sources[0]
    assert src.page == 7
    assert src.section == "Clausula 4"
    assert src.chunk_index == 3
    assert src.rrf_score == 0.032787

    events = list(uc.execute_stream("Cual es el plazo?"))
    assert events[0][0] == "meta"
    deltas = [data for name, data in events if name == "delta"]
    assert deltas == ["El plazo es de ", "30 dias [Fuente 1]."]
    assert events[-1] == ("done", "El plazo es de 30 dias [Fuente 1].")
