import unicodedata

from app.application.chat.ports.chat_history_repository import ChatHistoryRepository
from app.application.chat.ports.llm_provider import LLMProvider
from app.application.embeddings.use_cases.search_similar_chunks import SearchSimilarChunks
from app.domain.chat import AnswerSource, ChatAnswer
from app.shared.errors import ExternalServiceError


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
    "Lo siento, ahora no puedo consultar el documento porque el proveedor de inteligencia artificial "
    "no esta disponible o tiene credenciales invalidas. Revisa la configuracion de OpenAI/Azure OpenAI "
    "y vuelve a intentarlo."
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

    def execute(
        self,
        question: str,
        session_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> ChatAnswer:
        history = []
        if session_id and self._chat_history_repository:
            history = self._chat_history_repository.get_history(session_id, limit=12)
            self._chat_history_repository.save_user_message(session_id, question)

        try:
            mode = "summary" if self._is_summary_request(question) and document_ids else "qa"
            results = self._get_context(question, document_ids=document_ids, mode=mode)
            answer = self._llm_provider.answer_with_context(
                question,
                results,
                history=history,
                mode=mode,
            )
        except ExternalServiceError:
            results = []
            answer = ASSISTANT_ERROR_ANSWER

            if session_id and self._chat_history_repository:
                self._chat_history_repository.save_assistant_message(session_id, answer, [])

            return ChatAnswer(answer=answer, sources=[])

        sources = [
            AnswerSource(
                document_id=result.document_id,
                chunk_id=result.chunk_id,
                content=result.content,
                score=result.score,
                filename=result.filename,
            )
            for result in results
        ]

        if session_id and self._chat_history_repository:
            self._chat_history_repository.save_assistant_message(session_id, answer, sources)

        return ChatAnswer(answer=answer, sources=sources)

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
