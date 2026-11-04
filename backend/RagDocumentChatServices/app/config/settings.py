from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "rag-document-chat-service"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    database_url: str = "postgresql+psycopg://postgres:admin1234@localhost:5432/documents_db"

    groq_api_key: str = ""
    groq_chat_model: str = "openai/gpt-oss-20b"

    chat_completion_max_tokens: int = 2000
    chat_completion_temperature: float = 0.3
    chat_completion_timeout_seconds: int = 60

    document_storage_base_path: str = "./documents"
    max_chunk_size: int = 1200
    chunk_overlap: int = 160
    vector_search_limit: int = 5
    min_similarity_score: float = 0.0

    db_pool_min_size: int = 1
    db_pool_max_size: int = 10
    db_timeout_seconds: int = 30

    auth_jwt_public_key_path: str = "../AuthServices/public.pem"
    auth_jwt_algorithm: str = "RS256"
    internal_service_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
