# Production image for AWS Lightsail, Fly.io, Railway, or any Docker host.
# Build from repo root: docker build -t ubyhost .
# Data lives on a mounted volume at UBYHOST_DATA_DIR (default /data).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UBYHOST_DATA_DIR=/data \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates sqlite3 age \
    && rm -rf /var/lib/apt/lists/*

COPY App/requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY App/ .
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

RUN useradd --create-home --uid 10001 ubyhost \
    && mkdir -p /data \
    && chown ubyhost:ubyhost /data

USER ubyhost
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"

ENTRYPOINT ["docker-entrypoint.sh"]
# --no-access-log: uvicorn's own access log writes the raw request line, which
# includes guest permalink tokens and query strings. The app logs one PII-free
# line per request instead (see app/main.py, OPS-3).
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
