from fastapi import APIRouter, Depends, HTTPException, Query

from app.application.use_cases.manage_transfers import ManageTransfers
from app.interfaces.api.v1.dependencies import get_transfer_use_case
from app.interfaces.api.v1.schemas.transfer_schema import CountResponse, Identifier, TransferCreateRequest, TransferPage, TransferResponse, TransferUpdateRequest

router = APIRouter(responses={
    400: {"description": "Invalid request body."},
    401: {"description": "Access token required."},
    404: {"description": "Transfer or document not found."},
    409: {"description": "State or progress conflicts with the current transfer."},
    413: {"description": "Request body exceeds 65536 bytes."},
    422: {"description": "Invalid request values."},
    500: {"description": "Operation failed."},
})


@router.get("/transfers", response_model=TransferPage)
def list_transfers(limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0, le=10000),
                   use_case: ManageTransfers = Depends(get_transfer_use_case)):
    page = use_case.list(limit, offset)
    return {**page, "items": [_transfer_response(transfer) for transfer in page["items"]]}


@router.post("/transfers", response_model=TransferResponse)
def create_transfer(payload: TransferCreateRequest, use_case: ManageTransfers = Depends(get_transfer_use_case)):
    return _transfer_response(use_case.create(payload))


@router.patch("/transfers/{transfer_id}", response_model=TransferResponse)
def update_transfer(transfer_id: Identifier, payload: TransferUpdateRequest, use_case: ManageTransfers = Depends(get_transfer_use_case)):
    transfer = use_case.update(transfer_id, payload)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found.")
    return _transfer_response(transfer)


@router.delete("/transfers/history", response_model=CountResponse)
def clear_transfer_history(use_case: ManageTransfers = Depends(get_transfer_use_case)):
    return CountResponse(count=use_case.clear_history())


def _transfer_response(transfer) -> TransferResponse:
    return TransferResponse(
        transfer_id=str(transfer.transfer_id),
        owner_user_id=transfer.owner_user_id,
        document_id=transfer.document_id,
        filename=transfer.filename,
        direction=transfer.direction,
        status=transfer.status,
        progress=transfer.progress,
        size_bytes=transfer.size_bytes,
        metadata=transfer.metadata_ or {},
        created_at=transfer.created_at,
        updated_at=transfer.updated_at,
    )
