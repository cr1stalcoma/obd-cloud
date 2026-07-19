#!/usr/bin/env python3
"""Read ESP32 OBD JSON from COM port and push heartbeats to OBD Cloud API."""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

try:
    import serial
except ImportError:
    print("pip install pyserial httpx", file=sys.stderr)
    raise


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def main() -> None:
    api_url = env("PUBLIC_API_URL", "https://obd.lexora.by").rstrip("/")
    scanner_id = env("SCANNER_ID", "565300")
    scanner_secret = env("SCANNER_SECRET")
    com_port = env("COM_PORT", "COM3")

    if not scanner_secret:
        print("Set SCANNER_SECRET in environment (openssl rand -hex 16)", file=sys.stderr)
        sys.exit(1)

    print(f"Bridge → {api_url} scanner={scanner_id} port={com_port}", file=sys.stderr)

    last_error_at = 0.0
    with serial.Serial(com_port, 115200, timeout=1) as ser:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            body = {
                "scanner_id": scanner_id,
                "secret": scanner_secret,
                "payload": payload,
            }
            try:
                response = httpx.post(f"{api_url}/v1/heartbeat", json=body, timeout=15.0)
                if response.status_code == 403:
                    print("ERROR: invalid SCANNER_SECRET", file=sys.stderr)
                elif response.status_code >= 400:
                    now = time.time()
                    if now - last_error_at > 30:
                        detail = response.text[:300]
                        print(
                            f"heartbeat HTTP {response.status_code}: {detail}",
                            file=sys.stderr,
                        )
                        last_error_at = now
                else:
                    kind = payload.get("type", "?")
                    print(f"ok heartbeat ({kind})", file=sys.stderr)
            except httpx.HTTPError as exc:
                now = time.time()
                if now - last_error_at > 30:
                    print(f"network error: {exc}", file=sys.stderr)
                    last_error_at = now


if __name__ == "__main__":
    main()
