# Use the official Python slim image
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in Cloud Run logs
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Configure uv environment variables
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# Copy dependency files first for better caching
COPY uv.lock pyproject.toml ./

# Install dependencies without installing the project
RUN uv sync --locked --no-install-project

# Copy application code
COPY . .

# Install the project
RUN uv sync --locked

# Set PATH to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run will set the PORT environment variable
# Default to 8080 for local testing
ENV PORT=8080

# Run the application using the virtual environment
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT