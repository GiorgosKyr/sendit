from sendit.core.errors import BusinessRuleError, NotFoundError
from sendit.core.money import to_decimal


class AccountNotFoundError(NotFoundError):
    code = "ACCOUNT_NOT_FOUND"

    def __init__(self, account_id: str) -> None:
        super().__init__(f"Account {account_id} not found", details={"account_id": account_id})


class InsufficientFundsError(BusinessRuleError):
    code = "INSUFFICIENT_FUNDS"

    def __init__(self, account_id: str, balance_minor: int, requested_minor: int) -> None:
        balance, requested = to_decimal(balance_minor), to_decimal(requested_minor)
        super().__init__(
            f"Account {account_id} has balance {balance} but {requested} was requested",
            details={
                "account_id": account_id,
                "balance": str(balance),
                "requested": str(requested),
            },
        )
