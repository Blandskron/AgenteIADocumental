from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "google-drive-import-service"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    database_url: str = "postgresql+psycopg://postgres:admin1234@localhost:5432/documents_db"
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10
    db_timeout_seconds: int = 30

    auth_jwt_public_key_path: str = "../AuthServices/public.pem"
    auth_jwt_algorithm: str = "RS256"

    google_oauth_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID"),
    )
    google_oauth_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET"),
    )
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:3000/documents",
        validation_alias=AliasChoices("GOOGLE_DRIVE_REDIRECT_URI", "GOOGLE_OAUTH_REDIRECT_URI"),
    )
    google_oauth_scopes: str = Field(
        default="https://www.googleapis.com/auth/drive.file",
        validation_alias=AliasChoices("GOOGLE_OAUTH_SCOPES", "GOOGLE_DRIVE_OAUTH_SCOPES"),
    )
    google_oauth_token_url: str = "https://oauth2.googleapis.com/token"
    google_oauth_authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_drive_api_base_url: str = "https://www.googleapis.com/drive/v3"
    google_token_encryption_key: str = ""

    rag_document_base_url: str = "http://localhost:8003"
    request_timeout_seconds: int = 90
    max_import_files: int = 25

    @property
    def google_oauth_scope_list(self) -> list[str]:
        clean = (self.google_oauth_scopes or "").strip()
        if not clean:
            return ["https://www.googleapis.com/auth/drive.file"]
        if clean.startswith("["):
            import json

            parsed = json.loads(clean)
            return [str(scope) for scope in parsed if str(scope).strip()]
        return [scope for scope in clean.replace(",", " ").split() if scope]


@lru_cache
def get_settings() -> Settings:
    return Settings()
