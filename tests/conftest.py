from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

# The two model modules are imported for their side effect: registering every table on
# Base.metadata so create_all builds the full schema (ledger_entries references transfers).
from sendit.accounts import models as _accounts_models  # noqa: F401
from sendit.db.base import Base
from sendit.db.session import build_engine, build_session_factory
from sendit.transfers import models as _transfers_models  # noqa: F401


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Fresh in-memory database per test: fast, isolated, no files left behind."""
    engine = build_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with build_session_factory(engine)() as session:
        yield session
