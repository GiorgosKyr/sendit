from sqlalchemy import select
from sqlalchemy.orm import Session

from sendit.transfers.models import Transfer


class TransferRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, transfer: Transfer) -> Transfer:
        self.session.add(transfer)
        self.session.flush()
        return transfer

    def get(self, transfer_id: str) -> Transfer | None:
        return self.session.get(Transfer, transfer_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Transfer | None:
        stmt = select(Transfer).where(Transfer.idempotency_key == idempotency_key)
        return self.session.execute(stmt).scalar_one_or_none()
