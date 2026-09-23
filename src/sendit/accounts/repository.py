"""Data access only. Repositories never commit; the service owns the transaction."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from sendit.accounts.models import Account, LedgerEntry


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, account: Account) -> Account:
        self.session.add(account)
        self.session.flush()  # assigns defaults (id, timestamps) without committing
        return account

    def get(self, account_id: str) -> Account | None:
        return self.session.get(Account, account_id)

    def get_for_update(self, account_id: str) -> Account | None:
        """Load a row with a write lock (``SELECT ... FOR UPDATE``) for the rest of the transaction.

        SQLite has no row locks and ignores this, but it serialises writers anyway. On PostgreSQL
        the lock prevents two concurrent debits from both reading the same stale balance.
        """
        stmt = select(Account).where(Account.id == account_id).with_for_update()
        return self.session.execute(stmt).scalar_one_or_none()


class LedgerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_for_account(self, account_id: str, *, limit: int, offset: int) -> list[LedgerEntry]:
        stmt = (
            select(LedgerEntry)
            .where(LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.execute(stmt).scalars())
