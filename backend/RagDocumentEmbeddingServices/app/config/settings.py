from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "rag-document-embedding-service"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
    )

    database_url: str

    document_storage_base_path: str = "./documents"
    max_chunk_size: int = Field(default=1200, gt=0)
    chunk_overlap: int = Field(default=160, ge=0)

    auth_jwt_public_key_path: str = "../AuthServices/public.pem"
    auth_jwt_algorithm: str = "RS256"
    auth_identity_url: str = "http://127.0.0.1:8001/api/users/me/"

    @model_validator(mode="after")
    def validate_chunk_overlap(self):
        if self.chunk_overlap >= self.max_chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than MAX_CHUNK_SIZE.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
