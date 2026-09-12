# Production-style image for Fly.io, Railway, or a VPS.
# Build from repo root: docker build -t ubyhost .
# Run with a mounted volume at /data and UBYHOST_DATA_DIR=/data.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UBYHOST_DATA_DIR=/data \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY App/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY App/ .

RUN useradd --create-home --uid 10001 ubyhost \
    && mkdir -p /data \
    && chown ubyhost:ubyhost /data

USER ubyhost
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
