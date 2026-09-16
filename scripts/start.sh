#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; source .env; set +a; fi
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true; wait "$api_pid" 2>/dev/null || true' EXIT
npm --prefix frontend run dev -- --host 127.0.0.1
