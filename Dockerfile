# Build stage
FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
# git is often needed for installing deps from git
# build-essential/gcc for compiling C extensions if wheels aren't available
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage layer caching
COPY requirements.txt .

# Install python dependencies
# --user install to easy copy to final stage
# --no-warn-script-location to suppress path warnings
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable:
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY src/ ./src/
# We might need these if they are referenced, but usually src is enough if main is there.
# The project structure has src/main.py, so usually we run from root.

# Set environment variables to optimize python execution in container
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing pyc files
# PYTHONUNBUFFERED: Ensures console output is streamed directly (good for logs)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Port configuration
ENV PORT=8000
EXPOSE 8000

# Run the application
# Using uvicorn directly. 
# For EKS/production, this is often wrapped in a shell script or just the command.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

