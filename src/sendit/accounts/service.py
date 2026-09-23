"""Business rules for accounts. Knows nothing about HTTP."""

from decimal import Decimal

import structlog
from sqlalchemy.orm import Session

from sendit.accounts.exceptions import AccountNotFoundError, InsufficientFundsError
from sendit.accounts.models import Account, EntryType, LedgerEntry
from sendit.accounts.repository import AccountRepository, LedgerRepository
from sendit.accounts.schemas import CreateAccountRequest
from sendit.core.money import to_minor_units

log = structlog.get_logger()


class AccountService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.ledger = LedgerRepository(session)

    # ----- use cases (each one is a transaction boundary) --------------------------------------

    def create(self, request: CreateAccountRequest) -> Account:
        account = self.accounts.add(
            Account(owner_name=request.owner_name, currency=request.currency, balance_minor=0)
        )
        if request.initial_deposit > 0:
            self.apply_credit(
                account, to_minor_units(request.initial_deposit), description="Initial deposit"
            )
        self.session.commit()
        log.info("account.created", account_id=account.id, currency=account.currency)
        return account

    def get(self, account_id: str) -> Account:
        account = self.accounts.get(account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    def list_entries(self, account_id: str, *, limit: int, offset: int) -> list[LedgerEntry]:
        self.get(account_id)  # 404 if the account does not exist
        return self.ledger.list_for_account(account_id, limit=limit, offset=offset)

    def credit(self, account_id: str, amount: Decimal, description: str | None = None) -> Account:
        account = self.get_for_update(account_id)
        self.apply_credit(account, to_minor_units(amount), description=description)
        self.session.commit()
        return account

    def debit(self, account_id: str, amount: Decimal, description: str | None = None) -> Account:
        account = self.get_for_update(account_id)
        self.apply_debit(account, to_minor_units(amount), description=description)
        self.session.commit()
        return account

    # ----- building blocks used inside a caller-owned transaction (no commit here) --------------

    def get_for_update(self, account_id: str) -> Account:
        account = self.accounts.get_for_update(account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        return account

    def apply_credit(
        self,
        account: Account,
        amount_minor: int,
        *,
        transfer_id: str | None = None,
        description: str | None = None,
    ) -> LedgerEntry:
        account.balance_minor += amount_minor
        return self._record(account, EntryType.CREDIT, amount_minor, transfer_id, description)

    def apply_debit(
        self,
        account: Account,
        amount_minor: int,
        *,
        transfer_id: str | None = None,
        description: str | None = None,
    ) -> LedgerEntry:
        if account.balance_minor < amount_minor:
            raise InsufficientFundsError(account.id, account.balance_minor, amount_minor)
        account.balance_minor -= amount_minor
        return self._record(account, EntryType.DEBIT, amount_minor, transfer_id, description)

    def _record(
        self,
        account: Account,
        entry_type: EntryType,
        amount_minor: int,
        transfer_id: str | None,
        description: str | None,
    ) -> LedgerEntry:
        return self.ledger.add(
            LedgerEntry(
                account_id=account.id,
                entry_type=entry_type,
                amount_minor=amount_minor,
                balance_after_minor=account.balance_minor,
                transfer_id=transfer_id,
                description=description,
            )
        )
