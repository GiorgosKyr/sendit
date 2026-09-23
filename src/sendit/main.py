from fastapi import FastAPI

from sendit.api.health import router as health_router


def create_app() -> FastAPI:
    """Application factory.

    Building the app inside a function (instead of at import time) lets tests and
    other entry points construct fresh, independently configured instances.
    """
    app = FastAPI(
        title="sendit",
        description="Microservice for managing financial accounts and fund transfers.",
        version="0.1.0",
    )
    app.include_router(health_router)
    return app


app = create_app()
