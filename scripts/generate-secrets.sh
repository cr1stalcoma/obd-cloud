#!/usr/bin/env bash
# Generate secrets for .env (run locally, paste into VPS .env)
set -euo pipefail

echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
echo "BOT_INTERNAL_TOKEN=$(openssl rand -hex 32)"
python3 - <<'PY'
from cryptography.fernet import Fernet
print(f"ENCRYPTION_KEY={Fernet.generate_key().decode()}")
PY
echo "SCANNER_SECRET=$(openssl rand -hex 16)"
