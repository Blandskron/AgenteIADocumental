from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "document-library-service"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    database_url: str = "postgresql+psycopg://document_library_runtime@localhost:5432/documents_db"

    db_pool_min_size: int = Field(default=1, ge=1, le=100)
    db_pool_max_size: int = Field(default=10, ge=1, le=100)
    db_timeout_seconds: int = Field(default=30, ge=1, le=300)

    auth_jwt_public_key_path: str = "../AuthServices/public.pem"
    auth_jwt_algorithm: str = "RS256"

    @model_validator(mode="after")
    def validate_pool_bounds(self):
        if self.db_pool_min_size > self.db_pool_max_size:
            raise ValueError("DB_POOL_MIN_SIZE cannot exceed DB_POOL_MAX_SIZE.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
