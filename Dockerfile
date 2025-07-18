# Multi-stage build for UV with compiled dependencies
# Builder stage - includes all build dependencies
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies for grpcio and other compiled packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    python3-dev \
    pkg-config \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust for building packages like jiter (OpenAI dependency)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Configure uv environment variables for optimal builds
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Set working directory
WORKDIR /app

# Copy dependency files first for better Docker layer caching
COPY uv.lock pyproject.toml ./

# Install dependencies (no project install yet)
RUN uv sync --locked --no-install-project

# Copy application code
COPY . .

# Install the project
RUN uv sync --locked

# Runtime stage - minimal image with only runtime dependencies
FROM python:3.11-slim-bookworm

# Allow statements and log messages to immediately appear in Cloud Run logs
ENV PYTHONUNBUFFERED=1

# Copy the entire app directory with virtual environment from builder
COPY --from=builder /app /app

# Set working directory
WORKDIR /app

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