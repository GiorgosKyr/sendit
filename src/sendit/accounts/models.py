import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sendit.db.base import Base, TimestampMixin, UtcDateTime, utcnow


def new_id() -> str:
    return str(uuid.uuid4())


class EntryType(enum.StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class Account(TimestampMixin, Base):
    """A customer account. ``balance_minor`` is a cache of the ledger, maintained by the service."""

    __tablename__ = "accounts"
    __table_args__ = (
        # Database-level guard for the "no overdraft" invariant, in case any code path slips.
        CheckConstraint("balance_minor >= 0", name="ck_accounts_balance_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    balance_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LedgerEntry(Base):
    """One immutable line in an account's history. Never updated, never deleted."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_ledger_entries_amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, native_enum=False, length=10), nullable=False
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, nullable=False)
