FROM python:3.11-slim

# uv, copied from its official image so the version is pinned and reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    SENDIT_DATABASE_URL=sqlite:////data/sendit.db \
    SENDIT_APP_ENV=docker

WORKDIR /app

# 1. Dependencies only: this layer is cached until pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# 2. Application code.
COPY src ./src
RUN uv sync --locked --no-dev

# 3. Never run as root. /data holds the SQLite file and is mounted as a volume by compose.
RUN useradd --create-home --uid 1000 sendit \
    && mkdir -p /data \
    && chown -R sendit:sendit /app /data
USER sendit

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "sendit.main:app", "--host", "0.0.0.0", "--port", "8000"]
