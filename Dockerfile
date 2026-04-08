FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

RUN mkdir -p /app/data/attachments

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["sh", "-c", "uvicorn email_automation.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
