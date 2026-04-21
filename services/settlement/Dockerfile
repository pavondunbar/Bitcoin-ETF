FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Deterministic Python runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/shared

# Copy application
COPY . /app
COPY shared /shared

# Base runtime deps (stable CCP microservice baseline)
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    kafka-python \
    psycopg2-binary \
    pydantic

# Optional service-specific deps
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

CMD ["python", "services/settlement/main.py"]
