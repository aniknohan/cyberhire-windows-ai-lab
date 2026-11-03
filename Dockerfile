# CyberHire website: one container serving the React site and the FastAPI engine on $PORT.
# Build: docker build -t cyberhire-web .     Run: see render.yaml for the environment variables.

FROM node:22-bookworm-slim AS web
WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY frontend/package.json frontend/yarn.lock frontend/
RUN cd frontend && npx --yes yarn@1.22.22 install --frozen-lockfile --network-timeout 600000
COPY frontend frontend
COPY backend/lib/seed_data.py backend/lib/seed_data.py
COPY scripts/bundle_images.py scripts/bundle_images.py
# Interviewer photos are bundled into the site when they can be downloaded (falls back to their web addresses).
RUN python3 scripts/bundle_images.py || true
RUN cd frontend && npx --yes yarn@1.22.22 build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOC_MODE=web SOC_FRONTEND_DIR=/app/frontend/dist SOC_DATA_DIR=/var/data COOKIE_SECURE=1 PORT=8000
WORKDIR /app/backend
COPY backend/requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt && mkdir -p /var/data
COPY backend/ .
COPY --from=web /src/backend/lib/seed_data.py lib/seed_data.py
COPY --from=web /src/frontend/dist /app/frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/',timeout=4)"
# One worker on purpose: the built-in database and rate limits live in this process.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 30"]
