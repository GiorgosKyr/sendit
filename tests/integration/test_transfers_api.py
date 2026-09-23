"""HTTP-level tests: prove the wiring (routers, dependencies, error handlers, headers) works.

Business rules themselves are covered by the unit tests; these stay deliberately few.
"""

import uuid

from fastapi.testclient import TestClient

ACCOUNTS = "/api/v1/accounts"
TRANSFERS = "/api/v1/transfers"


def create_account(client: TestClient, owner: str, deposit: str = "0") -> str:
    response = client.post(ACCOUNTS, json={"owner_name": owner, "initial_deposit": deposit})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_transfer_happy_path(client: TestClient) -> None:
    alice = create_account(client, "Alice", "100.00")
    bob = create_account(client, "Bob")
    body = {"source_account_id": alice, "destination_account_id": bob, "amount": "30.00"}

    response = client.post(TRANSFERS, json=body, headers={"Idempotency-Key": "happy-1"})

    assert response.status_code == 201
    transfer = response.json()
    assert transfer["status"] == "COMPLETED"
    assert transfer["amount"] == "30.00"
    assert response.headers["X-Correlation-ID"]

    assert client.get(f"{ACCOUNTS}/{alice}").json()["balance"] == "70.00"
    assert client.get(f"{ACCOUNTS}/{bob}").json()["balance"] == "30.00"

    alice_entries = client.get(f"{ACCOUNTS}/{alice}/transactions").json()["items"]
    assert alice_entries[0]["type"] == "DEBIT"
    assert alice_entries[0]["transfer_id"] == transfer["id"]

    replay = client.post(TRANSFERS, json=body, headers={"Idempotency-Key": "happy-1"})
    assert replay.status_code == 200
    assert replay.json()["id"] == transfer["id"]
    assert client.get(f"{ACCOUNTS}/{alice}").json()["balance"] == "70.00"


def test_insufficient_funds_returns_error_contract(client: TestClient) -> None:
    alice = create_account(client, "Alice", "10.00")
    bob = create_account(client, "Bob")

    response = client.post(
        TRANSFERS,
        json={"source_account_id": alice, "destination_account_id": bob, "amount": "10.01"},
        headers={"Idempotency-Key": "poor-1", "X-Correlation-ID": "trace-abc"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "INSUFFICIENT_FUNDS"
    assert payload["error"]["details"] == {
        "account_id": alice,
        "balance": "10.00",
        "requested": "10.01",
    }
    assert payload["correlation_id"] == "trace-abc"
    assert response.headers["X-Correlation-ID"] == "trace-abc"
    assert client.get(f"{ACCOUNTS}/{alice}").json()["balance"] == "10.00"


def test_unknown_account_returns_404_contract(client: TestClient) -> None:
    missing = str(uuid.uuid4())

    response = client.get(f"{ACCOUNTS}/{missing}")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "ACCOUNT_NOT_FOUND"
    assert payload["error"]["details"] == {"account_id": missing}
    assert payload["correlation_id"]
