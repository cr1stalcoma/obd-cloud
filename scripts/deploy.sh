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

if grep -q '^DATABASE_URL=' .env 2>/dev/null; then
  echo "ERROR: Remove DATABASE_URL from .env — it overrides compose and breaks Alembic."
  echo "       Keep only POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB."
  exit 1
fi

pg_user="$(grep -E '^POSTGRES_USER=' .env | head -1 | cut -d= -f2- | tr -d '\r\"' | xargs)"
if [ -z "$pg_user" ]; then
  pg_user="obd"
fi
if [ "$pg_user" = "postgres" ]; then
  echo "ERROR: POSTGRES_USER=postgres but obd-cloud expects POSTGRES_USER=obd (matches existing volume)."
  echo "       Fix .env: POSTGRES_USER=obd and POSTGRES_PASSWORD=<same as when volume was created>"
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
sleep 8
if ! curl -sf http://127.0.0.1:8100/health >/dev/null; then
  echo "API not healthy. Last logs:"
  docker logs --tail 120 obd-cloud-api 2>&1 || true
  docker compose ps
  exit 1
fi

docker compose ps
echo "API ok: http://127.0.0.1:8100/health"
