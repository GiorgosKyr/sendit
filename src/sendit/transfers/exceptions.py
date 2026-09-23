from sendit.core.errors import BusinessRuleError, ConflictError, NotFoundError


class TransferNotFoundError(NotFoundError):
    code = "TRANSFER_NOT_FOUND"

    def __init__(self, transfer_id: str) -> None:
        super().__init__(f"Transfer {transfer_id} not found", details={"transfer_id": transfer_id})


class SameAccountTransferError(BusinessRuleError):
    code = "SAME_ACCOUNT_TRANSFER"

    def __init__(self, account_id: str) -> None:
        super().__init__(
            "Source and destination accounts must differ", details={"account_id": account_id}
        )


class CurrencyMismatchError(BusinessRuleError):
    code = "CURRENCY_MISMATCH"

    def __init__(self, source_currency: str, destination_currency: str) -> None:
        super().__init__(
            f"Cannot transfer {source_currency} into a {destination_currency} account",
            details={
                "source_currency": source_currency,
                "destination_currency": destination_currency,
            },
        )


class IdempotencyConflictError(ConflictError):
    code = "IDEMPOTENCY_CONFLICT"

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            "Idempotency-Key was already used with a different request payload",
            details={"idempotency_key": idempotency_key},
        )
