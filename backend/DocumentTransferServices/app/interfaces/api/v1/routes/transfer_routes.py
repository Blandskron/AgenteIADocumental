from fastapi import APIRouter, Depends, HTTPException, Query

from app.application.use_cases.manage_transfers import ManageTransfers
from app.interfaces.api.v1.dependencies import get_transfer_use_case
from app.interfaces.api.v1.schemas.transfer_schema import CountResponse, TransferCreateRequest, TransferResponse, TransferUpdateRequest

router = APIRouter()


@router.get("/transfers", response_model=list[TransferResponse])
def list_transfers(limit: int = Query(default=50, ge=1, le=200), use_case: ManageTransfers = Depends(get_transfer_use_case)):
    return [_transfer_response(transfer) for transfer in use_case.list(limit)]


@router.post("/transfers", response_model=TransferResponse)
def create_transfer(payload: TransferCreateRequest, use_case: ManageTransfers = Depends(get_transfer_use_case)):
    return _transfer_response(use_case.create(payload))


@router.patch("/transfers/{transfer_id}", response_model=TransferResponse)
def update_transfer(transfer_id: str, payload: TransferUpdateRequest, use_case: ManageTransfers = Depends(get_transfer_use_case)):
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
