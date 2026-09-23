from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from sendit.core.errors import ErrorResponse
from sendit.db.session import get_session
from sendit.transfers.schemas import TransferRequest, TransferResponse
from sendit.transfers.service import TransferService

router = APIRouter(prefix="/api/v1/transfers", tags=["transfers"])


def get_transfer_service(session: Annotated[Session, Depends(get_session)]) -> TransferService:
    return TransferService(session)


TransferServiceDep = Annotated[TransferService, Depends(get_transfer_service)]

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        description="Client-generated unique key (e.g. a UUID). Retrying with the same key and "
        "payload returns the original transfer instead of creating a second one.",
    ),
]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Transfer funds between two accounts",
    responses={
        status.HTTP_200_OK: {
            "model": TransferResponse,
            "description": "Replay of an already-completed transfer (same Idempotency-Key)",
        },
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Account not found"},
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Idempotency-Key reused with a different payload",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "Validation failed, insufficient funds, same account, currency mismatch",
        },
    },
)
def create_transfer(
    body: TransferRequest,
    idempotency_key: IdempotencyKey,
    service: TransferServiceDep,
    response: Response,
) -> TransferResponse:
    transfer, created = service.transfer(body, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return TransferResponse.from_model(transfer)


@router.get(
    "/{transfer_id}",
    summary="Get a transfer",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Transfer not found"}
    },
)
def get_transfer(transfer_id: str, service: TransferServiceDep) -> TransferResponse:
    return TransferResponse.from_model(service.get(transfer_id))
