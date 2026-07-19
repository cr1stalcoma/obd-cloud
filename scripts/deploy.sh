#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Create .env from .env.example first"
  exit 1
fi

# Quick sanity checks
missing=0
for key in POSTGRES_PASSWORD BOT_INTERNAL_TOKEN ENCRYPTION_KEY TELEGRAM_BOT_TOKEN; do
  if ! grep -q "^${key}=." .env; then
    echo "Missing or empty ${key} in .env"
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  exit 1
fi

if ! python3 - <<'PY' 2>/dev/null; then
from cryptography.fernet import Fernet
import os
for line in open(".env"):
    if line.startswith("ENCRYPTION_KEY="):
        key = line.strip().split("=", 1)[1]
        Fernet(key.encode())
        break
else:
    raise SystemExit(1)
PY
  echo "ENCRYPTION_KEY must be a valid Fernet key."
  echo "Generate: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
  exit 1
fi

docker compose pull || true
docker compose build --pull
docker compose up -d

echo "--- waiting for API ---"
sleep 5
if ! curl -sf http://127.0.0.1:8100/health >/dev/null; then
  echo "API not healthy yet. Last logs:"
  docker logs --tail 80 obd-cloud-api || true
  docker compose ps
  exit 1
fi

docker compose ps
echo "API ok: http://127.0.0.1:8100/health"
