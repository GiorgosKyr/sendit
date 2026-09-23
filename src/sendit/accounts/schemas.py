"""Request/response DTOs: the API contract, deliberately separate from the ORM models."""

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from sendit.accounts.models import Account, EntryType, LedgerEntry
from sendit.core.money import Amount, to_decimal


class CreateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    owner_name: str = Field(min_length=1, max_length=100, examples=["Maria Georgiou"])
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$", examples=["EUR"])
    initial_deposit: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=15, decimal_places=2, examples=["250.00"]
    )


class AmountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    amount: Amount = Field(examples=["25.50"])
    description: str | None = Field(default=None, max_length=200, examples=["Salary"])


class AccountResponse(BaseModel):
    id: str
    owner_name: str
    currency: str
    balance: Decimal
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, account: Account) -> Self:
        return cls(
            id=account.id,
            owner_name=account.owner_name,
            currency=account.currency,
            balance=to_decimal(account.balance_minor),
            created_at=account.created_at,
            updated_at=account.updated_at,
        )


class LedgerEntryResponse(BaseModel):
    id: str
    account_id: str
    type: EntryType
    amount: Decimal
    balance_after: Decimal
    transfer_id: str | None
    description: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, entry: LedgerEntry) -> Self:
        return cls(
            id=entry.id,
            account_id=entry.account_id,
            type=entry.entry_type,
            amount=to_decimal(entry.amount_minor),
            balance_after=to_decimal(entry.balance_after_minor),
            transfer_id=entry.transfer_id,
            description=entry.description,
            created_at=entry.created_at,
        )


class LedgerEntryListResponse(BaseModel):
    items: list[LedgerEntryResponse]
    limit: int
    offset: int
