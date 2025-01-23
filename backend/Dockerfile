FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY backend ./backend

RUN pip install uv
RUN uv sync

ENV FAINDER_DEMO_HOME=/app
EXPOSE 8000

CMD ["uv", "run", "fastapi", "dev", "backend/main.py", "--host", "0.0.0.0", "--port", "8000"]
