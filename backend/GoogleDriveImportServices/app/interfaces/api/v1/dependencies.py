from fastapi import Request

from app.application.use_cases.manage_google_drive_imports import ManageGoogleDriveImports
from app.config.settings import get_settings
from app.infrastructure.database.repositories.google_drive_repository_pg import GoogleDriveRepository
from app.infrastructure.documents.document_upload_client import DocumentUploadClient
from app.infrastructure.google.drive_client import GoogleDriveClient
from app.infrastructure.google.token_cipher import TokenCipher


def get_google_drive_use_case(request: Request) -> ManageGoogleDriveImports:
    settings = get_settings()
    repository = GoogleDriveRepository(request.app.state.database)
    return ManageGoogleDriveImports(
        repository=repository,
        google_client=GoogleDriveClient(settings),
        document_client=DocumentUploadClient(settings),
        token_cipher=TokenCipher(settings.google_token_encryption_key),
        settings=settings,
    )
