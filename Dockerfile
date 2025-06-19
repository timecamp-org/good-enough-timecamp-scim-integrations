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

# Copy and make entrypoint script executable
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create var directory for outputs
RUN mkdir -p var/logs

# Set environment variable to ensure Python output is not buffered
ENV PYTHONUNBUFFERED=1

# Set the entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command
CMD ["help"] 