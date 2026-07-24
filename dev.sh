#!/usr/bin/env bash
# Foreman — start the whole stack for local dev/demo.
#   Neo4j (Docker) + FastAPI (:8000) + web frontend (:5173)
set -e
cd "$(dirname "$0")"

echo "▸ Neo4j…"
docker compose up -d

echo "▸ loading project graph…"
./.venv/bin/python -m src.db --load

echo "▸ API on :8000…"
./.venv/bin/uvicorn backend.main:app --port 8000 &
API_PID=$!
trap "kill $API_PID 2>/dev/null" EXIT

echo "▸ web on :5173  (open http://localhost:5173)"
cd web && npm run dev
