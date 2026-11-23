from collections.abc import Iterator
import re
import unicodedata
from dataclasses import replace

from app.application.chat.ports.chat_history_repository import ChatHistoryRepository
from app.application.chat.ports.llm_provider import LLMProvider
from app.application.embeddings.use_cases.search_similar_chunks import SearchSimilarChunks
from app.domain.chat import AnswerSource, ChatAnswer
from app.shared.constants import MAX_CONTEXT_CHUNKS, MAX_CONTEXT_CHUNK_LENGTH, MAX_HISTORY_MESSAGES
from app.shared.errors import ExternalServiceError

_PAGE_MARKER_RE = re.compile(r"\[page\s+(\d+)\]", re.IGNORECASE)

INSUFFICIENT_EVIDENCE_ANSWER = (
    "No encontré evidencia suficiente en los documentos autorizados para responder esta consulta. "
    "Verifica que los documentos relevantes estén cargados y seleccionados, o reformula tu pregunta."
)


SUMMARY_KEYWORDS = (
    "resumen",
    "resume",
    "resumir",
    "sintesis",
    "sintetiza",
    "analiza",
    "analisis",
    "explica el documento",
    "de que trata",
    "de que se trata",
)

ASSISTANT_ERROR_ANSWER = (
    "No se pudo consultar el documento. Revisa la configuración de Groq y la disponibilidad "
    "del modelo de embeddings local, y vuelve a intentarlo."
)


class AskDocumentChat:
    def __init__(
        self,
        search_similar_chunks: SearchSimilarChunks,
        llm_provider: LLMProvider,
        chat_history_repository: ChatHistoryRepository | None = None,
    ) -> None:
        self._search_similar_chunks = search_similar_chunks
        self._llm_provider = llm_provider
        self._chat_history_repository = chat_history_repository

    @staticmethod
    def _extract_source(result) -> AnswerSource:
        meta = result.metadata or {}
        raw_page = meta.get("page")
        page: int | None = None
        if isinstance(raw_page, int) and raw_page >= 1:
            page = raw_page
        elif isinstance(raw_page, str) and raw_page.isdigit() and int(raw_page) >= 1:
            page = int(raw_page)
        else:
            match = _PAGE_MARKER_RE.search(result.content or "")
            if match:
                page = int(match.group(1))

        raw_section = meta.get("section")
        section = raw_section.strip() if isinstance(raw_section, str) and raw_section.strip() else None
        raw_rrf = meta.get("rrf_score")
        rrf_score = float(raw_rrf) if isinstance(raw_rrf, (int, float)) else None

        return AnswerSource(
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            content=result.content,
            score=result.score,
            filename=result.filename,
            chunk_index=result.chunk_index,
            page=page,
            section=section,
            rrf_score=rrf_score,
        )

    def execute(
        self,
        question: str,
        session_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> ChatAnswer:
        history = []
        if session_id and self._chat_history_repository:
            history = self._chat_history_repository.get_user_history(session_id, limit=MAX_HISTORY_MESSAGES)

        try:
            mode = "summary" if self._is_summary_request(question) and document_ids else "qa"
            results = self._get_context(question, document_ids=document_ids, mode=mode)
            results = [
                replace(result, content=result.content[:MAX_CONTEXT_CHUNK_LENGTH])
                for result in results[:MAX_CONTEXT_CHUNKS]
            ]
            if not results:
                answer = INSUFFICIENT_EVIDENCE_ANSWER
                if session_id and self._chat_history_repository:
                    self._chat_history_repository.save_turn(session_id, question, answer, [])
                return ChatAnswer(answer=answer, sources=[], provider_status="insufficient_evidence")

            answer = self._llm_provider.answer_with_context(
                question,
                results,
                history=history,
                mode=mode,
            )
        except ExternalServiceError as exc:
            return ChatAnswer(
                answer=ASSISTANT_ERROR_ANSWER,
                sources=[],
                provider_status=exc.provider_status,
            )

        sources = [self._extract_source(result) for result in results]

        if session_id and self._chat_history_repository:
            self._chat_history_repository.save_turn(session_id, question, answer, sources)

        return ChatAnswer(answer=answer, sources=sources)

    def execute_stream(
        self,
        question: str,
        session_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> Iterator[tuple[str, object]]:
        """Yields real-time SSE tuples: ('meta', {'provider_status', 'sources'}), ('delta', text), ('done', full_text)."""
        history = []
        if session_id and self._chat_history_repository:
            history = self._chat_history_repository.get_user_history(session_id, limit=MAX_HISTORY_MESSAGES)

        try:
            mode = "summary" if self._is_summary_request(question) and document_ids else "qa"
            results = self._get_context(question, document_ids=document_ids, mode=mode)
            results = [
                replace(result, content=result.content[:MAX_CONTEXT_CHUNK_LENGTH])
                for result in results[:MAX_CONTEXT_CHUNKS]
            ]
        except ExternalServiceError as exc:
            yield ("meta", {"provider_status": exc.provider_status, "sources": []})
            yield ("delta", ASSISTANT_ERROR_ANSWER)
            yield ("done", ASSISTANT_ERROR_ANSWER)
            return

        if not results:
            yield ("meta", {"provider_status": "insufficient_evidence", "sources": []})
            yield ("delta", INSUFFICIENT_EVIDENCE_ANSWER)
            if session_id and self._chat_history_repository:
                self._chat_history_repository.save_turn(session_id, question, INSUFFICIENT_EVIDENCE_ANSWER, [])
            yield ("done", INSUFFICIENT_EVIDENCE_ANSWER)
            return

        sources = [self._extract_source(result) for result in results]
        yield ("meta", {"provider_status": "ok", "sources": sources})

        chunks_emitted: list[str] = []
        stream_fn = getattr(self._llm_provider, "stream_answer_with_context", None)
        try:
            if callable(stream_fn):
                for delta in stream_fn(question, results, history=history, mode=mode):
                    if delta:
                        chunks_emitted.append(delta)
                        yield ("delta", delta)
            else:
                full = self._llm_provider.answer_with_context(question, results, history=history, mode=mode)
                chunks_emitted.append(full)
                yield ("delta", full)
        except ExternalServiceError:
            if not chunks_emitted:
                chunks_emitted.append(ASSISTANT_ERROR_ANSWER)
                yield ("delta", ASSISTANT_ERROR_ANSWER)

        full_answer = "".join(chunks_emitted)
        if session_id and self._chat_history_repository:
            self._chat_history_repository.save_turn(session_id, question, full_answer, sources)
        yield ("done", full_answer)

    def _get_context(
        self,
        question: str,
        document_ids: list[str] | None,
        mode: str,
    ):
        if mode == "summary" and document_ids:
            document_context = self._search_similar_chunks.get_document_context(
                document_ids=document_ids,
                limit_per_document=16,
            )
            if document_context:
                return document_context
        return self._search_similar_chunks.execute(question, document_ids=document_ids)

    def _is_summary_request(self, question: str) -> bool:
        normalized = unicodedata.normalize("NFKD", question.lower()).encode("ascii", "ignore").decode("ascii")
        return any(keyword in normalized for keyword in SUMMARY_KEYWORDS)
