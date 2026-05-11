# Multi-stage build for TrackIt

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY . /app/

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Add local user bin to PATH
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . /app/

# Create necessary directories
RUN mkdir -p logs media staticfiles


# Expose port
EXPOSE 8000
RUN chmod 777 entrypoint.sh

# Default command
ENTRYPOINT [ "bash", "entrypoint.sh" ]