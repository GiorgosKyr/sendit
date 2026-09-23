import logging

import structlog


def configure_logging(level: str) -> None:
    """Emit one JSON object per log line.

    ``merge_contextvars`` is what makes correlation IDs work: the middleware binds the ID
    into a context variable once, and every log call in that request picks it up automatically.
    """
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
