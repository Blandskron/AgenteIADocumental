from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "conversation-service"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"],
    )

    database_url: str

    auth_jwt_public_key_path: str = "../AuthServices/public.pem"
    auth_jwt_algorithm: str = "RS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()
