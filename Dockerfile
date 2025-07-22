# syntax=docker/dockerfile:1

# Use Python slim image for better compatibility
FROM python:3.12-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 jobx

# Install pip and uv
RUN pip install --no-cache-dir --upgrade pip==24.0 uv==0.4.18

# Set working directory
WORKDIR /app

# Copy project files
COPY --chown=jobx:jobx pyproject.toml README.md ./
COPY --chown=jobx:jobx jobx ./jobx

# Install dependencies
RUN uv pip install --system --no-cache -e .

# Switch to non-root user
USER jobx

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command
CMD ["jobx", "--help"]

# Labels
LABEL maintainer="jobx" \
      description="Modern job scraping library for LinkedIn and Indeed" \
      version="1.0.0"