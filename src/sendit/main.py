from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from sendit.accounts.router import router as accounts_router
from sendit.api.health import router as health_router
from sendit.core.config import Settings, get_settings
from sendit.core.correlation import CorrelationIdMiddleware
from sendit.core.errors import register_exception_handlers
from sendit.core.logging import configure_logging
from sendit.db.base import Base
from sendit.db.session import build_engine, build_session_factory
from sendit.transfers.router import router as transfers_router

log = structlog.get_logger()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    Building the app inside a function (instead of at import time) lets tests and other entry
    points construct fresh instances with their own settings, e.g. an in-memory database.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(engine)
        log.info("startup", env=settings.app_env)
        yield
        engine.dispose()

    app = FastAPI(
        title="sendit",
        description="Microservice for managing financial accounts and fund transfers.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = build_session_factory(engine)

    app.add_middleware(CorrelationIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(accounts_router)
    app.include_router(transfers_router)
    return app


app = create_app()
