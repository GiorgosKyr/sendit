from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from sendit.db.base import Base
from sendit.db.session import build_engine, build_session_factory


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
