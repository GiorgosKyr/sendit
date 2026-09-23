import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sendit.accounts.models import new_id
from sendit.db.base import Base, UtcDateTime, utcnow


class TransferStatus(enum.StrEnum):
    """Only COMPLETED is produced today (transfers are synchronous).

    Kept as an enum so PENDING / FAILED can be added when transfers become asynchronous.
    """

    COMPLETED = "COMPLETED"


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_transfers_amount_positive"),
        CheckConstraint(
            "source_account_id != destination_account_id", name="ck_transfers_distinct_accounts"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Client-supplied key; the UNIQUE index is what makes retries safe even under a race.
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    # Hash of the request payload, to detect the same key being reused for a different transfer.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    destination_account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id"), nullable=False, index=True
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus, native_enum=False, length=20), nullable=False
    )
    reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, nullable=False)
