from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from sendit.accounts.exceptions import InsufficientFundsError
from sendit.accounts.models import EntryType
from sendit.accounts.schemas import AmountRequest, CreateAccountRequest
from sendit.accounts.service import AccountService


@pytest.fixture
def service(session: Session) -> AccountService:
    return AccountService(session)


def test_create_with_initial_deposit_records_credit_entry(service: AccountService) -> None:
    account = service.create(
        CreateAccountRequest(owner_name="Maria", initial_deposit=Decimal("250.00"))
    )

    entries = service.list_entries(account.id, limit=10, offset=0)
    assert account.balance_minor == 25_000
    assert account.currency == "EUR"
    assert len(entries) == 1
    assert entries[0].entry_type == EntryType.CREDIT
    assert entries[0].amount_minor == 25_000
    assert entries[0].balance_after_minor == 25_000


def test_credit_increases_balance_and_records_entry(service: AccountService) -> None:
    account = service.create(CreateAccountRequest(owner_name="Maria"))

    updated = service.credit(account.id, Decimal("10.50"), description="Salary")

    assert updated.balance_minor == 1_050
    entry = service.list_entries(account.id, limit=10, offset=0)[0]
    assert entry.entry_type == EntryType.CREDIT
    assert entry.balance_after_minor == 1_050
    assert entry.description == "Salary"


def test_debit_decreases_balance(service: AccountService) -> None:
    account = service.create(
        CreateAccountRequest(owner_name="Maria", initial_deposit=Decimal("100.00"))
    )

    updated = service.debit(account.id, Decimal("40.25"))

    assert updated.balance_minor == 5_975
    newest = service.list_entries(account.id, limit=10, offset=0)[0]
    assert newest.entry_type == EntryType.DEBIT
    assert newest.balance_after_minor == 5_975


def test_debit_over_balance_is_rejected_and_balance_unchanged(service: AccountService) -> None:
    account = service.create(
        CreateAccountRequest(owner_name="Maria", initial_deposit=Decimal("10.00"))
    )

    with pytest.raises(InsufficientFundsError) as exc_info:
        service.debit(account.id, Decimal("10.01"))

    assert exc_info.value.details == {
        "account_id": account.id,
        "balance": "10.00",
        "requested": "10.01",
    }
    assert service.get(account.id).balance_minor == 1_000
    assert len(service.list_entries(account.id, limit=10, offset=0)) == 1


@pytest.mark.parametrize("amount", ["0", "-5.00", "1.234", "abc"])
def test_amount_request_rejects_invalid_amounts(amount: str) -> None:
    with pytest.raises(ValidationError):
        AmountRequest(amount=amount)
