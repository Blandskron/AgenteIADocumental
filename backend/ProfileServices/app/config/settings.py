from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    app_env: str = "local"
    app_name: str = "profile-service"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    database_url: str = Field(repr=False)

    db_pool_min_size: int = Field(default=1, ge=1, le=100)
    db_pool_max_size: int = Field(default=10, ge=1, le=100)
    db_timeout_seconds: int = Field(default=30, ge=1, le=300)

    auth_jwt_public_key_path: Path
    auth_jwt_algorithm: Literal["RS256"] = "RS256"
    profile_uploads_dir: Path

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value):
        try:
            url = make_url(value)
            valid = url.drivername == "postgresql+psycopg" and url.host and url.database and url.username
        except Exception:
            valid = False
        if not valid:
            raise ValueError("DATABASE_URL must identify a PostgreSQL psycopg database.")
        return value

    @field_validator("auth_jwt_public_key_path", "profile_uploads_dir")
    @classmethod
    def validate_absolute_path(cls, value):
        if not value.is_absolute():
            raise ValueError("An absolute path is required.")
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values):
        for value in values:
            try:
                url = urlsplit(value)
                valid = (url.scheme in {"http", "https"} and url.hostname and url.port != 0
                         and not url.username and not url.password and not url.path
                         and not url.query and not url.fragment and "*" not in value
                         and not any(character.isspace() for character in value))
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths or credentials.")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_pool(self):
        if self.db_pool_min_size > self.db_pool_max_size:
            raise ValueError("DB_POOL_MIN_SIZE cannot exceed DB_POOL_MAX_SIZE.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
