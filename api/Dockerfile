FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements_api.txt .
RUN pip install --no-cache-dir -r requirements_api.txt

COPY src/ ./src/
COPY api/ .

ENV PYTHONPATH=/app
EXPOSE 8000
