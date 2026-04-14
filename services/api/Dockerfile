FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY packages/scoring /build/packages/scoring
COPY services/agent /build/services/agent
COPY services/api /build/services/api
COPY rag /build/rag

RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -e /build/packages/scoring \
    && pip install --no-cache-dir -e /build/services/agent \
    && pip install --no-cache-dir -r /build/services/api/requirements.txt \
    && pip install --no-cache-dir -r /build/rag/requirements.txt

ENV PYTHONPATH=/build/services/api
WORKDIR /build/services/api

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
