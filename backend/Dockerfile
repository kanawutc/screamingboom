FROM python:3.12-slim

# Install system dependencies for C extensions (lxml, selectolax, psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast pip replacement)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency file first (layer caching)
COPY pyproject.toml .

# Install Python dependencies
RUN uv pip install --system --no-cache -e .

# Conditionally install Playwright and Chromium
ARG INSTALL_PLAYWRIGHT=0
RUN if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then \
      uv pip install --system --no-cache playwright && \
      playwright install chromium --with-deps; \
    fi

# Copy application code
COPY . .

# Create non-root user
RUN useradd -r -s /bin/false appuser && chown -R appuser:appuser /app
USER appuser

# Production entrypoint (gunicorn with uvicorn workers)
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
