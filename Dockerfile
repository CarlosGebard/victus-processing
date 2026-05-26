FROM ghcr.io/astral-sh/uv:0.11.16 AS uv

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY --from=uv /uv /uvx /usr/local/bin/

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgl1 \
        libxext6 \
        libxcb1

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data \
    && chown appuser:appuser /app/data

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY --chown=appuser:appuser config ./config
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser ops ./ops

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

USER appuser

VOLUME ["/app/data"]

ENTRYPOINT ["victus-processing"]
CMD ["--help"]
