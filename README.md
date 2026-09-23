# sendit

Accounts and transfers service. FastAPI + SQLAlchemy 2.0 on SQLite, Python 3.11.

You can create accounts, credit/debit them, list their transactions, and transfer money
between two accounts. Transfers are atomic and safe to retry.

## Running it

With uv:

```bash
uv sync
uv run uvicorn sendit.main:app --reload
```

With Docker:

```bash
docker compose up --build
```

Either way the API is on http://localhost:8000 and Swagger is at `/docs`.

Tests and lint:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Config is read from env vars (or a `.env` file, see `.env.example`). Defaults work out of the box.

| Var | Default |
|---|---|
| `SENDIT_DATABASE_URL` | `sqlite:///./sendit.db` |
| `SENDIT_LOG_LEVEL` | `INFO` |
| `SENDIT_APP_ENV` | `local` |

In Docker the db lives in a named volume under `/data`, so it survives restarts.
`docker compose down -v` deletes it.

## Endpoints

| Method | Path | |
|---|---|---|
| POST | `/api/v1/accounts` | create account (`owner_name`, optional `currency`, `initial_deposit`) |
| GET | `/api/v1/accounts/{id}` | account + balance |
| GET | `/api/v1/accounts/{id}/transactions` | ledger entries, newest first, `limit`/`offset` |
| POST | `/api/v1/accounts/{id}/credit` | deposit |
| POST | `/api/v1/accounts/{id}/debit` | withdraw |
| POST | `/api/v1/transfers` | transfer, needs an `Idempotency-Key` header |
| GET | `/api/v1/transfers/{id}` | |
| GET | `/health` | |

Amounts are strings like `"100.50"`, max two decimals. Never floats.

Quick run-through:

```bash
curl -s -X POST localhost:8000/api/v1/accounts -H 'Content-Type: application/json' \
  -d '{"owner_name": "Alice", "initial_deposit": "100.00"}'

curl -s -X POST localhost:8000/api/v1/accounts -H 'Content-Type: application/json' \
  -d '{"owner_name": "Bob"}'

curl -s -X POST localhost:8000/api/v1/transfers -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: abc-123' \
  -d '{"source_account_id": "<alice>", "destination_account_id": "<bob>", "amount": "30.00"}'
```

Send the last one twice with the same key and you get the same transfer back with a 200
instead of a second transfer.

### Errors

All errors look like this:

```json
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",
    "message": "Account 7f... has balance 10.00 but 25.00 was requested",
    "details": {"account_id": "7f...", "balance": "10.00", "requested": "25.00"}
  },
  "correlation_id": "c3a1..."
}
```

- 404: `ACCOUNT_NOT_FOUND`, `TRANSFER_NOT_FOUND`
- 409: `IDEMPOTENCY_CONFLICT` (same key, different body)
- 422: `VALIDATION_ERROR`, `INSUFFICIENT_FUNDS`, `SAME_ACCOUNT_TRANSFER`, `CURRENCY_MISMATCH`
- 500: `INTERNAL_ERROR`, no internals leaked, stack trace goes to the logs

The `correlation_id` is also in the `X-Correlation-ID` response header and on every log line
for that request. If you send the header yourself it gets reused.

## How it's put together

```
src/sendit/
  main.py         app factory, wires everything
  core/           config, json logging, correlation id middleware, error handling, money helpers
  db/             base model, engine, per-request session
  accounts/       models, schemas, repository, service, router
  transfers/      same layout
tests/
  unit/           services called directly on an in-memory db
  integration/    real app over http
```

Each feature folder has the full stack for that feature. Rules for the layers:

- routers parse the request, call one service method, return a response schema. No logic.
- services have all the business rules and decide when to commit. They raise domain
  exceptions, they don't know HTTP exists.
- repositories are just queries. They flush but never commit.
- Pydantic schemas and SQLAlchemy models are separate classes, so the API shape and the
  table shape can change independently.

The transfer service reuses the account service's `apply_debit` / `apply_credit`, which don't
commit, so a transfer is one transaction: transfer row + debit entry + credit entry, or nothing.

### Tables

```
accounts          id, owner_name, currency, balance_minor, created_at, updated_at
ledger_entries    id, account_id, entry_type (CREDIT/DEBIT), amount_minor, balance_after_minor,
                  transfer_id (nullable), description, created_at
transfers         id, idempotency_key (unique), request_hash, source_account_id,
                  destination_account_id, amount_minor, currency, status, reference, created_at
```

`ledger_entries` is append-only and is the actual history. `balance_minor` on the account is
just a running total of it. There are check constraints for `balance_minor >= 0` and
`amount_minor > 0` as a backstop.

## Decisions

Money is stored as integer cents and converted to `Decimal` at the API edge. SQLite has no
proper decimal type and floats are a no-go for money.

Transfers take an `Idempotency-Key` header. The key is unique in the db and stored together
with a sha256 of the request body. Retry with the same key and body: you get the original
transfer back. Same key, different body: 409. Because of the unique index this holds even if
two identical requests arrive at the same time; the loser gets the winner's transfer.

Both accounts are loaded with `SELECT ... FOR UPDATE`, always in sorted id order, before the
balance check. That's for Postgres really. SQLite ignores `FOR UPDATE` but only allows one
writer at a time so it's still correct there. The sorted order is what stops A->B and B->A
from deadlocking each other.

I went with sync SQLAlchemy and plain `def` endpoints. The SQLite driver is sync anyway,
transaction boundaries stay obvious, and FastAPI runs sync endpoints in a threadpool.

Feature folders instead of `routers/`, `services/`, `models/` folders. Easier to find things
and easier to pull a module out into its own service later.

## Assumptions

- One currency per account, default EUR. Transfers between different currencies are rejected.
- No overdraft.
- No auth. Anyone can hit any account. Obviously the first thing to add for real.
- `initial_deposit` on account creation is optional and gets recorded as a CREDIT entry.
- Credit and debit are exposed as endpoints, not just used internally.
- Transfers are synchronous and always end up `COMPLETED`. The status column exists so
  PENDING/FAILED can be added without a schema redesign.
- Rejected transfers aren't stored, the error response is the outcome.
- `Idempotency-Key` is required and never expires.
- Accounts can't be closed or deleted.
- Tables are created at startup with `create_all`, no migrations yet.
- Transaction list is newest first, offset pagination, limit 1-200.
- Timestamps are UTC.
- No transfer limits.

## Next steps

If this went further than a take-home, roughly in this order:

- auth (JWT on the routers + owner check in the services)
- Postgres and Alembic
- store rejected transfers with a reason
- async transfers with an outbox
- account status (frozen/closed) and limits
- CI running lint and tests on PRs
