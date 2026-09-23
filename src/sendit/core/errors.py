"""Domain error hierarchy and the single place where errors become HTTP responses.

Services raise ``DomainError`` subclasses and know nothing about HTTP. The handlers registered
here translate them into one consistent JSON contract::

    {"error": {"code": "...", "message": "...", "details": ...}, "correlation_id": "..."}
"""

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

log = structlog.get_logger()


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Documented in OpenAPI so clients see the exact error shape for every endpoint."""

    error: ErrorBody
    correlation_id: str | None


class DomainError(Exception):
    """Base class for all business errors. Subclasses set ``code`` and ``status_code``."""

    code = "DOMAIN_ERROR"
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT


class BusinessRuleError(DomainError):
    code = "BUSINESS_RULE_VIOLATION"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


def _error_response(
    request: Request, status_code: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "details": details},
            "correlation_id": getattr(request.state, "correlation_id", None),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        log.info("domain_error", code=exc.code, message=exc.message)
        return _error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in err["loc"]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "VALIDATION_ERROR",
            "Request validation failed",
            details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Full traceback goes to the logs; the client gets a generic message. The correlation id is
        # passed explicitly because this handler runs outside the middleware's context scope.
        log.exception(
            "unhandled_error", correlation_id=getattr(request.state, "correlation_id", None)
        )
        return _error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred",
        )
