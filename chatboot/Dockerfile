FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv

ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && python -m venv /app/.venv \
    && /app/.venv/bin/pip install --upgrade pip setuptools wheel \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN /app/.venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["/bin/sh", "-c", "/app/.venv/bin/uvicorn infrastructure.consultas.main:app --host 0.0.0.0 --port 8000 --workers ${CHATBOOT_WORKERS:-2} --ws-ping-interval 300 --ws-ping-timeout 300"]
