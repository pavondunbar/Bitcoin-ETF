FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Deterministic Python runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Copy full project (core/, services/, etc.)
COPY . /app

# Runtime deps
RUN pip install --no-cache-dir \
    kafka-python \
    psycopg2-binary

CMD ["python", "services/outbox/main.py"]
