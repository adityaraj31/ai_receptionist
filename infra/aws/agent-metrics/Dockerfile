FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AGENT_WORKER_URL=http://127.0.0.1:8081/worker \
    METRICS_INTERVAL_SECONDS=15

WORKDIR /app
COPY metrics_exporter.py /app/metrics_exporter.py

USER 65534:65534

ENTRYPOINT ["python", "/app/metrics_exporter.py"]
