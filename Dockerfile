FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project specification files
COPY pyproject.toml uv.lock ./

# Install dependencies into project virtual environment using uv sync
RUN uv sync --frozen --no-install-project

# Copy source code and migrations
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY main.py .

# Sync project
RUN uv sync --frozen

# Expose FastAPI application port
EXPOSE 8000

# Start Uvicorn web server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
