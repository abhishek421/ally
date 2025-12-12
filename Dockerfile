# syntax=docker/dockerfile:1.4

# ============================================
# Ally AI Copilot - Production Dockerfile
# Optimized for AWS EKS & GitHub Actions
# ============================================

# Build arguments
ARG PYTHON_VERSION=3.11
ARG ENVIRONMENT=production

# ---------------------------------------------
# Stage 1: Builder - Install dependencies
# ---------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies for compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies into a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Use BuildKit cache mount for faster rebuilds in CI
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip wheel setuptools && \
    pip install -r requirements.txt

# ---------------------------------------------
# Stage 2: Runtime - Final production image
# ---------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Labels for container registry and EKS
LABEL org.opencontainers.image.title="Ally AI Copilot" \
      org.opencontainers.image.description="LangGraph-based intelligent assistant for CRM" \
      org.opencontainers.image.vendor="Allyos" \
      org.opencontainers.image.source="https://github.com/allyos/ally"

# Runtime environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    # App settings
    HOST=0.0.0.0 \
    PORT=8000 \
    DEBUG=false \
    # Virtual env path
    PATH="/opt/venv/bin:$PATH" \
    # Reduce Python memory footprint
    PYTHONHASHSEED=random \
    MALLOC_ARENA_MAX=2

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security (required for EKS/Kubernetes best practices)
RUN groupadd --gid 1000 ally \
    && useradd --uid 1000 --gid ally --shell /bin/bash --create-home ally

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY --chown=ally:ally src/ ./src/
COPY --chown=ally:ally pyproject.toml ./

# Switch to non-root user
USER ally

# Expose the application port
EXPOSE 8000

# Health check for EKS/Kubernetes readiness and liveness probes
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with uvicorn
# Using exec form for proper signal handling in containers
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

