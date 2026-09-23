"""HTTP layer: parse the request, call one service method, return a DTO. No business rules here."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from sendit.accounts.schemas import (
    AccountResponse,
    AmountRequest,
    CreateAccountRequest,
    LedgerEntryListResponse,
    LedgerEntryResponse,
)
from sendit.accounts.service import AccountService
from sendit.core.errors import ErrorResponse
from sendit.db.session import get_session

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


def get_account_service(session: Annotated[Session, Depends(get_session)]) -> AccountService:
    return AccountService(session)


AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]

NOT_FOUND = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Account not found"}
}
RULE_VIOLATION = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "Validation failed or business rule violated (e.g. insufficient funds)",
    }
}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses=RULE_VIOLATION,
)
def create_account(body: CreateAccountRequest, service: AccountServiceDep) -> AccountResponse:
    return AccountResponse.from_model(service.create(body))


@router.get("/{account_id}", summary="Get account details", responses=NOT_FOUND)
def get_account(account_id: str, service: AccountServiceDep) -> AccountResponse:
    return AccountResponse.from_model(service.get(account_id))


@router.get(
    "/{account_id}/transactions",
    summary="List an account's transactions, newest first",
    responses=NOT_FOUND,
)
def list_transactions(
    account_id: str,
    service: AccountServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LedgerEntryListResponse:
    entries = service.list_entries(account_id, limit=limit, offset=offset)
    return LedgerEntryListResponse(
        items=[LedgerEntryResponse.from_model(e) for e in entries], limit=limit, offset=offset
    )


@router.post(
    "/{account_id}/credit",
    summary="Credit (deposit into) an account",
    responses={**NOT_FOUND, **RULE_VIOLATION},
)
def credit_account(
    account_id: str, body: AmountRequest, service: AccountServiceDep
) -> AccountResponse:
    return AccountResponse.from_model(service.credit(account_id, body.amount, body.description))


@router.post(
    "/{account_id}/debit",
    summary="Debit (withdraw from) an account",
    responses={**NOT_FOUND, **RULE_VIOLATION},
)
def debit_account(
    account_id: str, body: AmountRequest, service: AccountServiceDep
) -> AccountResponse:
    return AccountResponse.from_model(service.debit(account_id, body.amount, body.description))
