from fastapi import Depends, HTTPException, Request

from app.application.use_cases.manage_google_drive_imports import ManageGoogleDriveImports
from app.config.security import DriveUser, require_authenticated_user
from app.config.settings import Settings, get_settings
from app.infrastructure.database.repositories.google_drive_repository_pg import GoogleDriveRepository
from app.infrastructure.documents.document_upload_client import DocumentUploadClient
from app.infrastructure.google.drive_client import GoogleDriveClient
from app.infrastructure.google.token_cipher import TokenCipher


def require_enabled(current_user: DriveUser = Depends(require_authenticated_user), settings: Settings = Depends(get_settings)):
    if not settings.google_drive_enabled:
        raise HTTPException(status_code=503, detail="Google Drive integration is disabled.")


def get_google_drive_use_case(request: Request, current_user: DriveUser = Depends(require_authenticated_user),
                              settings: Settings = Depends(get_settings)):
    return ManageGoogleDriveImports(
        repository=GoogleDriveRepository(request.app.state.database, current_user),
        google_client=GoogleDriveClient(settings),
        document_client=DocumentUploadClient(settings),
        token_cipher=TokenCipher(settings.google_token_encryption_key) if settings.google_drive_enabled else None,
        settings=settings,
    )
