# Multi-stage build for minimal image size
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r smpp && useradd -r -g smpp smpp

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create app directory
WORKDIR /app

# Copy application code
COPY src /app/src/
COPY main.py /app/

# Change ownership
RUN chown -R smpp:smpp /app

# Switch to non-root user
USER smpp

# Expose ports
EXPOSE 2776 9091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python main.py healthcheck || exit 1

# Run application
CMD ["python", "main.py"]