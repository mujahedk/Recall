#!/usr/bin/env bash
# start.sh — one-shot convenience wrapper for local demo startup.
#
# Equivalent to: make db && make migrate && make dev
# Run from the repo root: bash scripts/start.sh
#
# Prerequisites:
#   - Docker running              (for Postgres)
#   - python3.12 installed        (brew install python@3.12)
#   - .venv set up                (make install)
#   - .env present with OPENAI_API_KEY + DATABASE_URL

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BIN="$REPO_ROOT/.venv/bin"

# ── Prerequisite checks ───────────────────────────────────────────────────────

if ! command -v docker &>/dev/null; then
  echo "ERROR: docker not found. Install Docker Desktop and try again."
  exit 1
fi

if ! command -v python3.12 &>/dev/null; then
  echo "ERROR: python3.12 not found."
  echo "  brew install python@3.12"
  exit 1
fi

if [ ! -f "$BIN/uvicorn" ]; then
  echo "ERROR: .venv not set up. Run:"
  echo "  make install"
  exit 1
fi

if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "ERROR: .env not found. Copy the example and fill in your key:"
  echo "  cp .env.example .env"
  exit 1
fi

# ── Start services ────────────────────────────────────────────────────────────

echo "Starting Postgres ..."
docker compose up -d

echo "Waiting for Postgres to be ready ..."
sleep 2

echo "Running migrations ..."
"$BIN/alembic" upgrade head

echo ""
echo "Starting Recall server ..."
echo "  Dashboard: http://localhost:8000"
echo "  API docs:  http://localhost:8000/docs"
echo ""
echo "In another terminal run 'make demo' to load sample data."
echo ""

exec "$BIN/uvicorn" app.main:app --reload
