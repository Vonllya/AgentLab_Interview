#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock.txt
npm --prefix frontend ci
docker build -t agentlab-runner:0.1 -f backend/Dockerfile .
