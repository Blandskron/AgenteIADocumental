from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True, populate_by_name=True)

    app_env: str = "local"
    app_name: str = "google-drive-import-service"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    database_url: str = Field(repr=False)

    db_pool_min_size: int = Field(default=1, ge=1, le=100)
    db_pool_max_size: int = Field(default=10, ge=1, le=100)
    db_timeout_seconds: int = Field(default=30, ge=1, le=300)


    auth_jwt_public_key_path: Path
    auth_jwt_algorithm: Literal["RS256"] = "RS256"

    google_token_key_id: str = Field(default="v1", pattern=r"^[A-Za-z0-9_-]{1,32}$")
    google_token_previous_keys: dict[str,str] = Field(default_factory=dict, repr=False)
    google_token_legacy_key_id: str | None = None
    google_picker_app_id: str = Field(default="", max_length=128)

    google_drive_enabled: bool = False
    google_oauth_client_id: str = Field(default="", validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID"))
    google_oauth_client_secret: str = Field(default="", repr=False, validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET"))
    google_oauth_redirect_uri: str = Field(default="http://localhost:3000/documents", validation_alias=AliasChoices("GOOGLE_DRIVE_REDIRECT_URI", "GOOGLE_OAUTH_REDIRECT_URI"))
    google_oauth_scopes: str = Field(default="https://www.googleapis.com/auth/drive.file", validation_alias=AliasChoices("GOOGLE_OAUTH_SCOPES", "GOOGLE_DRIVE_OAUTH_SCOPES"))
    google_oauth_token_url: str = "https://oauth2.googleapis.com/token"
    google_oauth_authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_drive_api_base_url: str = "https://www.googleapis.com/drive/v3"
    google_token_encryption_key: str = Field(default="", repr=False)
    rag_document_base_url: str = "http://rag-document-embedding-service:8000"
    request_timeout_seconds: int = Field(default=30, ge=1, le=90)
    max_import_files: int = Field(default=25, ge=1, le=25)

    @property
    def google_oauth_scope_list(self):
        return ["https://www.googleapis.com/auth/drive.file"]

    @field_validator("google_oauth_scopes")
    @classmethod
    def validate_scope(cls, value):
        if value != "https://www.googleapis.com/auth/drive.file":
            raise ValueError("Only the drive.file scope is supported.")
        return value

    @field_validator("google_oauth_token_url", "google_oauth_authorize_url", "google_drive_api_base_url")
    @classmethod
    def validate_google_endpoint(cls, value, info):
        expected = {"google_oauth_token_url": "https://oauth2.googleapis.com/token",
                    "google_oauth_authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                    "google_drive_api_base_url": "https://www.googleapis.com/drive/v3"}
        if value != expected[info.field_name]:
            raise ValueError("Google endpoint must be the supported HTTPS origin and path.")
        return value

    @field_validator("rag_document_base_url", "google_oauth_redirect_uri")
    @classmethod
    def validate_destination(cls, value):
        try:
            url = urlsplit(value)
            local = url.hostname in {"localhost", "127.0.0.1", "rag-document-embedding-service"}
            valid = (url.scheme == "https" or (url.scheme == "http" and local))
            valid = (valid and url.hostname and not url.username and not url.password
                     and not url.query and not url.fragment and url.port != 0
                     and not any(char.isspace() for char in value))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Destination must be HTTPS or a supported local development URL.")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_google_configuration(self):
        if self.google_drive_enabled:
            key = self.google_token_encryption_key
            if (not self.google_oauth_client_id or not self.google_oauth_client_secret
                    or len(key) < 32 or key.lower().startswith(("change", "local-", "example"))):
                raise ValueError("Enabled Drive requires OAuth credentials and an independent encryption secret.")
            redirect = urlsplit(self.google_oauth_redirect_uri)
            origin = f"{redirect.scheme}://{redirect.netloc}"
            if redirect.path not in {"/documents", "/applications/google-drive"} or origin not in self.cors_origins:
                raise ValueError("OAuth callback must use a supported path on an allowed frontend origin.")
            from app.infrastructure.google.token_cipher import TokenCipher
            TokenCipher.from_settings(self)
        return self

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

    @field_validator("auth_jwt_public_key_path")
    @classmethod
    def validate_absolute_path(cls, value):
        if value is not None and not value.is_absolute():
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
