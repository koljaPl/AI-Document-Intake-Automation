FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install project dependencies
COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY sample_documents/ ./sample_documents/

RUN pip install --upgrade pip && \
    pip install .

# Create volume mount points for input and output
VOLUME ["/data", "/output"]

ENTRYPOINT ["ai-intake"]
CMD ["--help"]
