from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "conversation-service"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    database_url: str = "postgresql+psycopg://postgres:admin1234@localhost:5432/documents_db"

    db_pool_min_size: int = 1
    db_pool_max_size: int = 10
    db_timeout_seconds: int = 30

    auth_jwt_public_key_path: str = "../AuthServices/public.pem"
    auth_jwt_algorithm: str = "RS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()
