import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from sendit.core.money import Amount, to_decimal
from sendit.transfers.models import Transfer, TransferStatus


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_account_id: str = Field(min_length=1, max_length=36)
    destination_account_id: str = Field(min_length=1, max_length=36)
    amount: Amount = Field(examples=["100.00"])
    reference: str | None = Field(default=None, max_length=200, examples=["Invoice 42"])

    def fingerprint(self) -> str:
        """Stable hash of the payload. Stored with the idempotency key so a retry with the same
        key but a *different* request can be detected and rejected."""
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


class TransferResponse(BaseModel):
    id: str
    source_account_id: str
    destination_account_id: str
    amount: Decimal
    currency: str
    status: TransferStatus
    reference: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, transfer: Transfer) -> Self:
        return cls(
            id=transfer.id,
            source_account_id=transfer.source_account_id,
            destination_account_id=transfer.destination_account_id,
            amount=to_decimal(transfer.amount_minor),
            currency=transfer.currency,
            status=transfer.status,
            reference=transfer.reference,
            created_at=transfer.created_at,
        )
