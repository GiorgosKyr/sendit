from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_IN_MEMORY_SQLITE = {"sqlite://", "sqlite:///:memory:"}


def build_engine(database_url: str) -> Engine:
    """Create the engine. SQLite needs a few tweaks that other databases do not:

    - ``check_same_thread=False``: FastAPI runs sync endpoints in a threadpool, so a pooled
      connection may be reused from a different thread than the one that opened it.
    - ``StaticPool`` for in-memory databases (tests): every thread must share the single
      connection, otherwise each one sees its own empty database.
    - ``PRAGMA foreign_keys=ON``: SQLite ignores foreign keys unless told otherwise.
    """
    is_sqlite = database_url.startswith("sqlite")
    kwargs: dict = {}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url in _IN_MEMORY_SQLITE:
            kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **kwargs)
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):  # noqa: ANN001
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after the service commits, so the router
    # can serialise them without an extra round trip to the database.
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request.

    The *service* decides when to commit. This dependency only guarantees that whatever was not
    committed is rolled back and the connection is returned to the pool.
    """
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
