"""Transfer lifecycle: validate -> lock -> debit -> credit -> record -> commit, exactly once."""

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sendit.accounts.service import AccountService
from sendit.core.money import to_minor_units
from sendit.transfers.exceptions import (
    CurrencyMismatchError,
    IdempotencyConflictError,
    SameAccountTransferError,
    TransferNotFoundError,
)
from sendit.transfers.models import Transfer, TransferStatus
from sendit.transfers.repository import TransferRepository
from sendit.transfers.schemas import TransferRequest

log = structlog.get_logger()


class TransferService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.transfers = TransferRepository(session)
        self.accounts = AccountService(session)

    def get(self, transfer_id: str) -> Transfer:
        transfer = self.transfers.get(transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        return transfer

    def transfer(self, request: TransferRequest, idempotency_key: str) -> tuple[Transfer, bool]:
        """Execute a transfer. Returns ``(transfer, created)``; ``created`` is False on a replay."""
        fingerprint = request.fingerprint()

        # 1. Idempotency: a retry of an already-completed request must not move money again.
        existing = self.transfers.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.request_hash != fingerprint:
                raise IdempotencyConflictError(idempotency_key)
            log.info("transfer.replayed", transfer_id=existing.id)
            return existing, False

        # 2. Cheap validation before touching the database.
        if request.source_account_id == request.destination_account_id:
            raise SameAccountTransferError(request.source_account_id)

        # 3. Lock both accounts in a deterministic order so two opposite transfers
        #    (A->B and B->A) can never deadlock each other. Raises 404 if either is missing.
        locked = {
            account_id: self.accounts.get_for_update(account_id)
            for account_id in sorted((request.source_account_id, request.destination_account_id))
        }
        source = locked[request.source_account_id]
        destination = locked[request.destination_account_id]

        if source.currency != destination.currency:
            raise CurrencyMismatchError(source.currency, destination.currency)

        # 4. Record the transfer, then move the money, then commit: one transaction.
        #    Any failure (e.g. insufficient funds) rolls everything back, so a rejected
        #    transfer leaves no trace.
        amount_minor = to_minor_units(request.amount)
        try:
            transfer = self.transfers.add(
                Transfer(
                    idempotency_key=idempotency_key,
                    request_hash=fingerprint,
                    source_account_id=source.id,
                    destination_account_id=destination.id,
                    amount_minor=amount_minor,
                    currency=source.currency,
                    status=TransferStatus.COMPLETED,
                    reference=request.reference,
                )
            )
            self.accounts.apply_debit(
                source, amount_minor, transfer_id=transfer.id, description=request.reference
            )
            self.accounts.apply_credit(
                destination, amount_minor, transfer_id=transfer.id, description=request.reference
            )
            self.session.commit()
        except IntegrityError:
            # Two identical requests raced past step 1: the UNIQUE index on idempotency_key
            # rejected the loser. Return the winner instead of failing the retry.
            self.session.rollback()
            winner = self.transfers.get_by_idempotency_key(idempotency_key)
            if winner is None:
                raise
            log.info("transfer.replayed", transfer_id=winner.id, race=True)
            return winner, False
        except Exception:
            self.session.rollback()
            raise

        log.info(
            "transfer.completed",
            transfer_id=transfer.id,
            source_account_id=source.id,
            destination_account_id=destination.id,
            amount=str(request.amount),
            currency=transfer.currency,
        )
        return transfer, True
