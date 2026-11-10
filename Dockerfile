FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WARMUP_ON_STARTUP=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies with lightweight CPU torch
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source, data manifests, and configuration
COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY data/ ./data/
COPY Docs/ ./Docs/
COPY evaluation/ ./evaluation/
COPY tests/ ./tests/

# Install application package in editable mode
RUN pip install --no-cache-dir -e .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
