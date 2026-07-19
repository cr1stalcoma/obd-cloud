# OBD Cloud

Docker stack: **PostgreSQL + Redis + FastAPI + Telegram bot**.

Subdomain: `https://obd.lexora.by` → API `:8100` on VPS.

## VPS deploy (185.244.50.80)

1. DNS: `obd.lexora.by` A → `185.244.50.80`

2. Secrets (never commit):
   ```bash
   cd obd-cloud
   bash scripts/generate-secrets.sh
   cp .env.example .env
   # paste secrets + TELEGRAM_BOT_TOKEN
   ```

3. **Rotate Telegram bot token** if it was exposed in chat (@BotFather → Revoke).

4. Nginx (alongside existing lexora site):
   ```bash
   sudo cp deploy/nginx-obd.lexora.by.conf /etc/nginx/sites-available/obd.lexora.by
   sudo ln -sf /etc/nginx/sites-available/obd.lexora.by /etc/nginx/sites-enabled/
   sudo certbot certonly --nginx -d obd.lexora.by
   sudo nginx -t && sudo systemctl reload nginx
   ```

5. Start stack:
   ```bash
   bash scripts/deploy.sh
   ```

## PC bridge (Windows)

```powershell
cd obd-cloud\bridge
pip install -r requirements.txt
$env:PUBLIC_API_URL="https://obd.lexora.by"
$env:SCANNER_ID="565300"
$env:SCANNER_SECRET="<same as in .env on VPS or first-run generated>"
$env:COM_PORT="COM3"
python obd_bridge.py
```

First heartbeat **registers** scanner `565300` with `SCANNER_SECRET`.

## Telegram

1. `/start` → код сканера `565300`
2. Cursor API key (message deleted)
3. `/status` — статус сканера
4. `/ask Что значит P0420?` — Composer 2.5 Fast

## Scale path

- `vehicle_wmi` + future ECU DB tables in Postgres
- `obd_snapshots` history for analytics
- Redis ready for queues / rate limits
- Separate `api` and `bot` containers → horizontal scale later
