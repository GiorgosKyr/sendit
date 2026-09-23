from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from sendit.accounts.exceptions import AccountNotFoundError, InsufficientFundsError
from sendit.accounts.models import Account, EntryType
from sendit.accounts.schemas import CreateAccountRequest
from sendit.accounts.service import AccountService
from sendit.transfers.exceptions import IdempotencyConflictError, SameAccountTransferError
from sendit.transfers.models import TransferStatus
from sendit.transfers.schemas import TransferRequest
from sendit.transfers.service import TransferService


@pytest.fixture
def accounts(session: Session) -> AccountService:
    return AccountService(session)


@pytest.fixture
def transfers(session: Session) -> TransferService:
    return TransferService(session)


@pytest.fixture
def alice(accounts: AccountService) -> Account:
    return accounts.create(CreateAccountRequest(owner_name="Alice", initial_deposit=Decimal("100")))


@pytest.fixture
def bob(accounts: AccountService) -> Account:
    return accounts.create(CreateAccountRequest(owner_name="Bob", initial_deposit=Decimal("20")))


def request(source: Account, destination: Account, amount: str) -> TransferRequest:
    return TransferRequest(
        source_account_id=source.id, destination_account_id=destination.id, amount=Decimal(amount)
    )


def test_successful_transfer_moves_funds_and_records_ledger_entries(
    transfers: TransferService, accounts: AccountService, alice: Account, bob: Account
) -> None:
    transfer, created = transfers.transfer(request(alice, bob, "30.00"), "key-1")

    assert created is True
    assert transfer.status == TransferStatus.COMPLETED
    assert accounts.get(alice.id).balance_minor == 7_000
    assert accounts.get(bob.id).balance_minor == 5_000

    alice_entry = accounts.list_entries(alice.id, limit=1, offset=0)[0]
    bob_entry = accounts.list_entries(bob.id, limit=1, offset=0)[0]
    assert (alice_entry.entry_type, alice_entry.amount_minor) == (EntryType.DEBIT, 3_000)
    assert (bob_entry.entry_type, bob_entry.amount_minor) == (EntryType.CREDIT, 3_000)
    assert alice_entry.transfer_id == bob_entry.transfer_id == transfer.id


def test_insufficient_funds_rejects_transfer_and_persists_nothing(
    transfers: TransferService, accounts: AccountService, alice: Account, bob: Account
) -> None:
    with pytest.raises(InsufficientFundsError):
        transfers.transfer(request(alice, bob, "100.01"), "key-2")

    assert accounts.get(alice.id).balance_minor == 10_000
    assert accounts.get(bob.id).balance_minor == 2_000
    assert transfers.transfers.get_by_idempotency_key("key-2") is None
    assert len(accounts.list_entries(alice.id, limit=10, offset=0)) == 1  # only the deposit


def test_same_account_is_rejected(transfers: TransferService, alice: Account) -> None:
    with pytest.raises(SameAccountTransferError):
        transfers.transfer(request(alice, alice, "1.00"), "key-3")


def test_unknown_destination_is_rejected(transfers: TransferService, alice: Account) -> None:
    body = TransferRequest(
        source_account_id=alice.id, destination_account_id="missing", amount=Decimal("1.00")
    )
    with pytest.raises(AccountNotFoundError):
        transfers.transfer(body, "key-4")


def test_idempotent_replay_and_conflict(
    transfers: TransferService, accounts: AccountService, alice: Account, bob: Account
) -> None:
    first, created_first = transfers.transfer(request(alice, bob, "10.00"), "key-5")
    replay, created_replay = transfers.transfer(request(alice, bob, "10.00"), "key-5")

    assert (created_first, created_replay) == (True, False)
    assert replay.id == first.id
    assert accounts.get(alice.id).balance_minor == 9_000  # money moved exactly once

    with pytest.raises(IdempotencyConflictError):
        transfers.transfer(request(alice, bob, "99.00"), "key-5")
