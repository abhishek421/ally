# Multi-stage build for smaller image size
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies with increased timeout and retries
# Split installation to avoid memory/pipe issues with large packages
RUN pip install --no-cache-dir --user --timeout=300 --retries=5 \
    langgraph>=1.0.0 \
    openai>=1.0.0 \
    anthropic>=0.34.0 \
    google-generativeai>=0.3.0

RUN pip install --no-cache-dir --user --timeout=300 --retries=5 \
    prisma>=0.11.0 \
    psycopg2-binary>=2.9.0 \
    boto3>=1.28.0 \
    redis>=5.0.0

RUN pip install --no-cache-dir --user --timeout=300 --retries=5 \
    "qdrant-client>=1.7.0" \
    "sentence-transformers>=2.2.0" \
    "rank-bm25>=0.2.2"

RUN pip install --no-cache-dir --user --timeout=300 --retries=5 \
    "pydantic>=2.0.0,<3.0.0" \
    python-dotenv>=1.0.0

RUN pip install --no-cache-dir --user --timeout=300 --retries=5 \
    fastapi>=0.100.0 \
    uvicorn>=0.23.0 \
    python-multipart>=0.0.6 \
    aiofiles>=23.0.0 \
    "python-jose[cryptography]>=3.3.0" \
    requests>=2.31.0

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies including Node.js for Prisma
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    libatomic1 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Generate Prisma client during build
RUN python -m prisma generate

# Expose the FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application (Prisma client already generated during build)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
