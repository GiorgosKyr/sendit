from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

# The two model modules are imported for their side effect: registering every table on
# Base.metadata so create_all builds the full schema (ledger_entries references transfers).
from sendit.accounts import models as _accounts_models  # noqa: F401
from sendit.core.config import Settings
from sendit.db.base import Base
from sendit.db.session import build_engine, build_session_factory
from sendit.main import create_app
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


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Full application against its own in-memory database.

    Entering the context runs the lifespan, which creates the tables; the app factory means
    no global state leaks between tests.
    """
    app = create_app(Settings(database_url="sqlite://", log_level="WARNING"))
    with TestClient(app) as client:
        yield client
