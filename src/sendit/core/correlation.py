import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_HEADER = "X-Correlation-ID"
_MAX_HEADER_LENGTH = 128


class CorrelationIdMiddleware:
    """Attach a correlation ID to every HTTP request.

    - Reuses the caller's ``X-Correlation-ID`` if present (so a gateway can propagate its own),
      otherwise generates one.
    - Binds it to structlog's context so every log line in the request carries it.
    - Exposes it on ``request.state.correlation_id`` for error responses.
    - Echoes it back in the response header so clients can quote it in support requests.

    Implemented as a pure ASGI middleware (rather than ``BaseHTTPMiddleware``) because that is the
    lightweight, recommended form and it plays well with context variables.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(CORRELATION_HEADER, "")
        correlation_id = incoming if 0 < len(incoming) <= _MAX_HEADER_LENGTH else uuid.uuid4().hex

        scope.setdefault("state", {})["correlation_id"] = correlation_id
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(CORRELATION_HEADER, correlation_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            structlog.contextvars.unbind_contextvars("correlation_id")
