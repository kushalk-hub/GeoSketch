# GeoSketch backend (FastAPI + SQLite) - optional, see ../docker-compose.yml
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so the layer is cached while the source changes.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# SQLite database volume + data directory (artworks, sample routes).
RUN mkdir -p /db /data

EXPOSE 8000

# 0.0.0.0 so the container is reachable from the ESP32-C3 on the LAN.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
