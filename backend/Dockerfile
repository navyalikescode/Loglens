FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# Railway, Render, etc. set $PORT; local Docker defaults to 8000
# exec + explicit sh -c so $PORT is expanded at container runtime and signals reach uvicorn
EXPOSE 8000
CMD ["/bin/sh", "-c", "exec uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
