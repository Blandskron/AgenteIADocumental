from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.application.chat.use_cases.ask_document_chat import AskDocumentChat
from app.application.embeddings.use_cases.search_similar_chunks import SearchSimilarChunks
from app.config.database import get_session
from app.config.security import require_authenticated_user
from app.config.settings import Settings, get_settings
from app.infrastructure.ai.embedding_provider_local import LocalEmbeddingProvider
from app.infrastructure.ai.llm_provider_groq import GroqLLMProvider
from app.infrastructure.database.repositories.chat_history_repository_pg import ChatHistoryRepositoryPg
from app.infrastructure.database.repositories.vector_repository_pgvector import VectorRepositoryPgVector


def build_embedding_provider() -> LocalEmbeddingProvider:
    return LocalEmbeddingProvider()


def build_llm_provider(settings: Settings) -> GroqLLMProvider:
    return GroqLLMProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_chat_model,
        max_tokens=settings.chat_completion_max_tokens,
        temperature=settings.chat_completion_temperature,
        timeout_seconds=settings.chat_completion_timeout_seconds,
    )


def get_ask_document_chat(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: dict = Depends(require_authenticated_user),
) -> AskDocumentChat:
    is_service = current_user.get("is_service", False)
    if not is_service:
        active_perms = current_user.get("active_permissions") or []
        is_super = (
            current_user.get("is_superuser")
            or current_user.get("is_superadmin")
            or "SUPERADMIN" in (current_user.get("roles") or [])
        )
        if not (is_super or "*" in active_perms or "use_chat" in active_perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para usar el chat conversacional.",
            )

    embedding_provider = build_embedding_provider()
    vector_repository = VectorRepositoryPgVector(session, current_user=current_user)
    search_similar_chunks = SearchSimilarChunks(
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        limit=settings.vector_search_limit,
        min_score=settings.min_similarity_score,
    )
    return AskDocumentChat(
        search_similar_chunks=search_similar_chunks,
        llm_provider=build_llm_provider(settings),
        chat_history_repository=ChatHistoryRepositoryPg(session, current_user=current_user),
    )
