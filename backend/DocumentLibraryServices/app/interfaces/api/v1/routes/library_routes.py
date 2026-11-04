from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.use_cases.manage_library import ManageLibrary
from app.interfaces.api.v1.dependencies import get_library_use_case
from app.interfaces.api.v1.schemas.library_schema import (
    ActionResponse,
    CountResponse,
    DeleteResponse,
    DocumentMoveRequest,
    DocumentResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderUpdateRequest,
)

router = APIRouter()


@router.get("/folders", response_model=list[FolderResponse])
def list_folders(parent_folder_id: str | None = None, use_case: ManageLibrary = Depends(get_library_use_case)):
    return [_folder_response(folder) for folder in use_case.list_folders(parent_folder_id)]


@router.post("/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(payload: FolderCreateRequest, use_case: ManageLibrary = Depends(get_library_use_case)):
    folder = use_case.create_folder(payload)
    if folder is None:
        raise HTTPException(status_code=404, detail="Parent folder not found.")
    return _folder_response(folder)


@router.patch("/folders/{folder_id}", response_model=FolderResponse)
def update_folder(folder_id: str, payload: FolderUpdateRequest, use_case: ManageLibrary = Depends(get_library_use_case)):
    folder = use_case.update_folder(folder_id, payload)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found.")
    return _folder_response(folder)


@router.delete("/folders/{folder_id}", response_model=DeleteResponse)
def delete_folder(folder_id: str, use_case: ManageLibrary = Depends(get_library_use_case)):
    return DeleteResponse(deleted=use_case.delete_folder(folder_id))


@router.get("/folders/{folder_id}/documents", response_model=list[DocumentResponse])
def folder_documents(folder_id: str, use_case: ManageLibrary = Depends(get_library_use_case)):
    return [_document_response(document) for document in use_case.list_folder_documents(folder_id)]


@router.post("/folders/{folder_id}/documents/{document_id}", response_model=DeleteResponse)
def add_document_to_folder(folder_id: str, document_id: str, use_case: ManageLibrary = Depends(get_library_use_case)):
    return DeleteResponse(deleted=use_case.add_document_to_folder(folder_id, document_id))


@router.delete("/folders/{folder_id}/documents/{document_id}", response_model=DeleteResponse)
def remove_document_from_folder(folder_id: str, document_id: str, use_case: ManageLibrary = Depends(get_library_use_case)):
    return DeleteResponse(deleted=use_case.remove_document_from_folder(folder_id, document_id))


@router.patch("/library/documents/{document_id}/folder", response_model=ActionResponse)
def move_document_to_folder(
    document_id: str,
    payload: DocumentMoveRequest,
    use_case: ManageLibrary = Depends(get_library_use_case),
):
    success = use_case.move_document_to_folder(document_id, payload.folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document or folder not found.")
    return ActionResponse(success=True)


@router.get("/library/recent", response_model=list[DocumentResponse])
def recent_documents(limit: int = Query(default=20, ge=1, le=100), use_case: ManageLibrary = Depends(get_library_use_case)):
    return [_document_response(document) for document in use_case.list_recent(limit)]


@router.get("/library/favorites", response_model=list[DocumentResponse])
def favorite_documents(use_case: ManageLibrary = Depends(get_library_use_case)):
    return [_document_response(document) for document in use_case.list_favorites()]


@router.post("/library/favorites/{document_id}", response_model=CountResponse)
def add_favorite(document_id: str, use_case: ManageLibrary = Depends(get_library_use_case)):
    return CountResponse(count=1 if use_case.add_favorite(document_id) else 0)


@router.delete("/library/favorites/{document_id}", response_model=CountResponse)
def remove_favorite(document_id: str, use_case: ManageLibrary = Depends(get_library_use_case)):
    return CountResponse(count=1 if use_case.remove_favorite(document_id) else 0)


def _folder_response(folder) -> FolderResponse:
    return FolderResponse(
        folder_id=str(folder.folder_id),
        name=folder.name,
        parent_folder_id=folder.parent_folder_id,
        owner_user_id=folder.owner_user_id,
        metadata=folder.metadata_ or {},
        document_count=getattr(folder, "document_count", 0),
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def _document_response(document) -> DocumentResponse:
    return DocumentResponse(
        document_id=str(document.document_id),
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status,
        chunk_count=getattr(document, "chunk_count", 0),
        updated_at=document.updated_at,
    )
