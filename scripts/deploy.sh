#!/usr/bin/env bash
# Run on VPS after git pull into ~/obdmarket-by/obd-cloud
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Create .env from .env.example first"
  exit 1
fi

docker compose pull || true
docker compose build --pull
docker compose up -d
docker compose ps
curl -sf http://127.0.0.1:8100/health && echo " API ok"
