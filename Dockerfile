# Optimized UV Dockerfile with minimal Rust dependencies
FROM python:3.11-bookworm

# Allow statements and log messages to immediately appear in Cloud Run logs
ENV PYTHONUNBUFFERED=1

# Install minimal Rust for jiter (OpenAI dependency) only
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:$PATH"

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Configure UV to install directly to system Python (no virtual env needed)
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Set working directory
WORKDIR /app

# Copy dependency files first for better Docker layer caching
COPY uv.lock pyproject.toml ./

# Install dependencies directly to system Python using UV
# Now with 95% fewer Rust dependencies (only jiter remains)
RUN uv sync --locked --no-dev

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Cloud Run will set the PORT environment variable
# Default to 8080 for local testing
ENV PORT=8080

# Run the application directly (no virtual env activation needed)
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT