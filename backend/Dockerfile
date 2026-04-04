# Multi-stage build for optimal image size
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash terraform \
    && chown -R terraform:terraform /app

# Copy installed dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY --chown=terraform:terraform backend/ .
COPY --chown=terraform:terraform requirements.txt .

# Ensure pip installed packages are in PATH and discoverable by non-root user
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/root/.local/lib/python3.12/site-packages
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER terraform

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

# Run the application
CMD ["python", "app.py"]
