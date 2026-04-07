FROM python:3.11-slim

# Install system dependencies for python-ldap
RUN apt-get update && apt-get install -y \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user and set ownership
RUN groupadd -g 1000 appuser \
    && useradd -u 1000 -g appuser -s /bin/sh -M appuser \
    && mkdir -p var/logs \
    && chown -R appuser:appuser /app

# Set environment variable to ensure Python output is not buffered
ENV PYTHONUNBUFFERED=1

# Run as non-root user
USER appuser

# Default command
CMD ["python", "--help"]