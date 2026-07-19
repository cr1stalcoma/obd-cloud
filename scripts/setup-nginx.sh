#!/usr/bin/env bash
# Nginx + Let's Encrypt for obd.lexora.by
# Run on VPS as root. Requires DNS A record: obd.lexora.by -> server IP
set -euo pipefail

DOMAIN=obd.lexora.by
REPO_DIR="${REPO_DIR:-$HOME/obd-cloud}"

echo "=== 1) DNS check ==="
if ! getent hosts "$DOMAIN" >/dev/null; then
  echo "ERROR: $DOMAIN does not resolve yet."
  echo "Add DNS A record: obd.lexora.by -> $(curl -s ifconfig.me || echo YOUR_VPS_IP)"
  exit 1
fi
echo "OK: $DOMAIN -> $(getent hosts "$DOMAIN" | awk '{print $1}')"

echo "=== 2) HTTP-only nginx (no SSL paths yet) ==="
mkdir -p /var/www/certbot
cp "$REPO_DIR/deploy/nginx-obd.lexora.by.init.conf" /etc/nginx/sites-available/obd.lexora.by
ln -sf /etc/nginx/sites-available/obd.lexora.by /etc/nginx/sites-enabled/obd.lexora.by
nginx -t
systemctl reload nginx

echo "=== 3) Let's Encrypt certificate ==="
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" --non-interactive --agree-tos -m admin@lexora.by || {
    echo "If email prompt failed, run manually:"
    echo "  certbot certonly --webroot -w /var/www/certbot -d $DOMAIN"
    exit 1
  }
fi

echo "=== 4) Enable HTTPS config ==="
cp "$REPO_DIR/deploy/nginx-obd.lexora.by.conf" /etc/nginx/sites-available/obd.lexora.by
nginx -t
systemctl reload nginx

echo "=== 5) Test ==="
curl -sf "https://$DOMAIN/health" && echo " OK"
