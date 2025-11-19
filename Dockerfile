# syntax=docker/dockerfile:1
# Multi-stage build for smaller image size
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building Python packages
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies with cache mount for speed
# Cache mount dramatically speeds up rebuilds by reusing downloaded packages
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --user -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies including Node.js for Prisma
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    libpq5 \
    curl \
    libatomic1 \
    nodejs \
    npm

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Generate Prisma client during build
# Cache Prisma CLI downloads to avoid re-downloading on every build
RUN --mount=type=cache,target=/root/.cache/prisma \
    python -m prisma generate

# Expose the FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application (Prisma client already generated during build)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
