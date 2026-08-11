# Foreman — one image, one service.
# Stage 1 builds the React app; stage 2 runs FastAPI and serves that build from
# the same origin. One URL, no CORS, no API base to configure.

# ---------------------------------------------------------------- web build
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ------------------------------------------------------------------ runtime
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY src/ src/
COPY data/ data/
COPY --from=web /web/dist web/dist

# Render/Fly inject PORT; default keeps `docker run -p 8000:8000` working.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
