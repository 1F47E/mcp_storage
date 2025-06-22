FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PostgreSQL and MySQL clients
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster Python package management
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY mcp_server/ ./mcp_server/
COPY mcp_client/ ./mcp_client/

# Install Python dependencies
RUN uv pip install --system -e .

# Expose the HTTP transport port
EXPOSE 5435

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5435/health', timeout=5)" || exit 1

# Run the server with HTTP transport on port 5435
CMD ["mcp-storage", "--transport", "http", "--port", "5435"]