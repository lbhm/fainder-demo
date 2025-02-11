FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install project into /app
WORKDIR /app

# Install compiler toolchain
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy the project into the image
ADD . /app

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000
ENTRYPOINT []
ARG FASTAPI_MODE=run

CMD fastapi ${FASTAPI_MODE} backend/main.py --host 0.0.0.0 --port 8000
