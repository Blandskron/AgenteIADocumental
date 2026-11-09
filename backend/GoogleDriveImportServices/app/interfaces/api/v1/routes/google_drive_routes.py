from fastapi import APIRouter, Depends, Query, HTTPException, Response

from app.config.security import DriveUser, bearer_token, owner_user_id, require_authenticated_user
from app.application.use_cases.manage_google_drive_imports import ManageGoogleDriveImports
from app.interfaces.api.v1.dependencies import get_google_drive_use_case, require_enabled
from app.interfaces.api.v1.schemas.google_drive_schema import (
    AuthUrlResponse, AuthUrlRequest, DisconnectRequest, GoogleDriveImportPage, GoogleDriveImportFilePage,
    GoogleDriveConnectRequest,
    GoogleDriveConnectionResponse,
    GoogleDriveImportFileResponse,
    GoogleDriveImportRequest,
    GoogleDriveImportResponse,
    GoogleDriveImportWithFilesResponse,
)

router = APIRouter()


@router.get("/google-drive/auth-url", dependencies=[Depends(require_enabled)], response_model=AuthUrlResponse)
def auth_url(
    return_url: str | None = Query(default=None),
    current_user: DriveUser = Depends(require_authenticated_user),
    use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case),
):
    raise HTTPException(status_code=410, detail="Start authorization with POST and PKCE.")


@router.post("/google-drive/auth-url", dependencies=[Depends(require_enabled)], response_model=AuthUrlResponse)
def start_authorization(payload: AuthUrlRequest, current_user: DriveUser = Depends(require_authenticated_user),
                        use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case)):
    return use_case.auth_url(owner_user_id(current_user), payload.code_challenge)


@router.post("/google-drive/disconnect", response_model=GoogleDriveConnectionResponse)
def disconnect(payload: DisconnectRequest, response: Response,
               current_user: DriveUser = Depends(require_authenticated_user),
               use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case)):
    status = use_case.disconnect(owner_user_id(current_user), payload.version)
    if status["grant_status"] == "REVOKE_PENDING":
        response.status_code = 202
    return status


@router.post("/google-drive/oauth/callback", dependencies=[Depends(require_enabled)], response_model=GoogleDriveConnectionResponse)
def connect_google_drive(
    payload: GoogleDriveConnectRequest,
    current_user: DriveUser = Depends(require_authenticated_user),
    use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case),
):
    return use_case.connect(owner_user_id(current_user), payload.code, payload.state, payload.code_verifier)


@router.get("/google-drive/connection", response_model=GoogleDriveConnectionResponse)
def connection_status(
    current_user: DriveUser = Depends(require_authenticated_user),
    use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case),
):
    return GoogleDriveConnectionResponse(**use_case.connected_status(owner_user_id(current_user)))


@router.post("/google-drive/imports", dependencies=[Depends(require_enabled)], response_model=GoogleDriveImportWithFilesResponse)
def create_import(
    payload: GoogleDriveImportRequest,
    current_user: DriveUser = Depends(require_authenticated_user),
    access_token: str = Depends(bearer_token),
    use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case),
):
    record, files = use_case.import_files(owner_user_id(current_user), access_token, payload)
    return GoogleDriveImportWithFilesResponse(**_import_payload(record), files=[_file_response(file) for file in files])


@router.get("/google-drive/imports", response_model=GoogleDriveImportPage)
def list_imports(
    limit: int = Query(default=25, ge=1, le=100),
    before: str | None = Query(default=None, min_length=1, max_length=1024),
    current_user: DriveUser = Depends(require_authenticated_user),
    use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case),
):
    rows, cursor = use_case.list_imports(owner_user_id(current_user), limit, before)
    return {"items": [_import_response(record) for record in rows], "next_cursor": cursor}


@router.get("/google-drive/imports/{import_id}", response_model=GoogleDriveImportResponse)
def get_import(
    import_id: str,
    current_user: DriveUser = Depends(require_authenticated_user),
    use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case),
):
    return _import_response(use_case.get_import(owner_user_id(current_user), import_id))


@router.get("/google-drive/imports/{import_id}/files", response_model=GoogleDriveImportFilePage)
def list_import_files(
    import_id: str,
    limit: int = Query(default=25, ge=1, le=100),
    after: str | None = Query(default=None, min_length=1, max_length=1024),
    current_user: DriveUser = Depends(require_authenticated_user),
    use_case: ManageGoogleDriveImports = Depends(get_google_drive_use_case),
):
    rows, cursor = use_case.page_import_files(owner_user_id(current_user), import_id, limit, after)
    return {"items": [_file_response(file) for file in rows], "next_cursor": cursor}


def _import_payload(record) -> dict:
    return {
        "import_id": str(record.import_id),
        "owner_user_id": record.owner_user_id,
        "status": record.status,
        "operation_id": record.operation_id,
        "version": record.version,
        "total_files": record.total_files,
        "processed_files": record.processed_files,
        "failed_files": record.failed_files,
        "metadata": _safe_metadata(record.metadata_, file=False),
        "error_message": "Google Drive import completed with errors." if record.error_message else None,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _import_response(record) -> GoogleDriveImportResponse:
    return GoogleDriveImportResponse(**_import_payload(record))


def _file_response(record) -> GoogleDriveImportFileResponse:
    return GoogleDriveImportFileResponse(
        import_file_id=str(record.import_file_id),
        import_id=str(record.import_id),
        google_file_id=record.google_file_id[:128],
        filename=record.filename[:200],
        mime_type=record.mime_type[:128],
        export_mime_type=record.export_mime_type[:128] if record.export_mime_type else None,
        size_bytes=record.size_bytes,
        status=record.status,
        document_id=record.document_id,
        metadata=_safe_metadata(record.metadata_, file=True),
        error_message="Google Drive file import completed with errors." if record.error_message else None,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _safe_metadata(value, *, file):
    value = value if isinstance(value, dict) else {}
    result = {}
    if not file:
        result["source"] = "google_drive"
        folder = value.get("folder_id")
        if isinstance(folder, str) and len(folder) <= 128:
            result["folder_id"] = folder
    else:
        status = value.get("document_status")
        if isinstance(status, str) and status in {"PENDING", "UPLOADED", "PROCESSING", "PROCESSED", "FAILED", "REVIEW_REQUIRED"}:
            result["document_status"] = status
        association = value.get("folder_association")
        if isinstance(association, dict) and isinstance(association.get("status"), str) and association.get("status") in {"COMPLETED", "FAILED"}:
            result["folder_association"] = {"status": association["status"]}
            folder = association.get("folder_id")
            if isinstance(folder, str) and len(folder) <= 128:
                result["folder_association"]["folder_id"] = folder
    return result
