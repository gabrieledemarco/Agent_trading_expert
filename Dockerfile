FROM python:3.11-slim

LABEL maintainer="TradingAgent Team"
LABEL description="Self-hosted multi-agent trading system"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p data/research_findings data/market_data models/versions specs tests trading_logs

# Expose port (Render injects $PORT=10000 at runtime)
EXPOSE 10000

# exec replaces sh so uvicorn is PID 1 — required for Render signal handling & port detection
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]