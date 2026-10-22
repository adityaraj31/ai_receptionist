# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.10.9 AS uv

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=120 \
    PATH="/app/.venv/bin:$PATH" \
    AGENT_HTTP_PORT=8081

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app

WORKDIR /app
COPY --from=uv /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY agent_tools.py api_client.py call_lifecycle.py clinic_repository.py \
     prompts.py recording.py transfer.py ./
COPY scripts ./scripts

RUN chown -R app:app /app

USER app
EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/', timeout=3)"]

CMD ["python", "-m", "src.receptionist_agent", "start"]
