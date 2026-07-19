from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.models import ObdSnapshot, Scanner, ScannerState, ScannerStatus, TelegramUser
from app.services.cursor import ask_cursor, validate_cursor_api_key


def hash_secret(secret: str) -> str:
    return bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_secret(secret: str, secret_hash: str) -> bool:
    try:
        return bcrypt.checkpw(secret.encode("utf-8"), secret_hash.encode("utf-8"))
    except ValueError:
        return False


SYSTEM_PROMPT = """Ты помощник в Telegram по автодиагностике.
Пользователь использует самодельный сканер: ESP32 + MCP2515, стандартный OBD-II (Mode 01/03/07/09), без баз Autocom.

Стиль ответа:
- по-русски, как нормальный механик в чате, не как отчёт
- без заголовков вроде «Кратко:», «Вывод:», «По данным:»
- без markdown (**жирный**, списки) — только plain text для Telegram
- обычно 2–4 предложения, развёрнуто — только если пользователь просит
- только факты из блока «Данные сканера»; не придумывай VIN, обороты, коды

Если сканер online, но ECU не отвечает — адаптер и облако работают, машина/зажигание/CAN пока не дали ответ."""


def map_heartbeat_state(payload: dict[str, Any]) -> ScannerState:
    msg_type = payload.get("type")
    if msg_type == "obd_error":
        return ScannerState.waiting
    if msg_type == "obd_snapshot":
        if payload.get("vin") or payload.get("rpm") is not None:
            return ScannerState.on_car
        return ScannerState.waiting
    return ScannerState.error


async def upsert_heartbeat(
    db: AsyncSession,
    scanner_id: str,
    secret: str,
    payload: dict[str, Any],
    wifi_ssid: str | None = None,
) -> None:
    scanner = await db.get(Scanner, scanner_id)
    if scanner is None:
        scanner = Scanner(id=scanner_id, secret_hash=hash_secret(secret))
        db.add(scanner)
        await db.flush()
    elif not verify_secret(secret, scanner.secret_hash):
        raise PermissionError("invalid scanner secret")

    state = map_heartbeat_state(payload)
    status = await db.get(ScannerStatus, scanner_id)
    if status is None:
        status = ScannerStatus(scanner_id=scanner_id)
        db.add(status)

    status.state = state
    status.bitrate = payload.get("bitrate")
    status.vin = payload.get("vin")
    status.manufacturer = payload.get("manufacturer")
    status.rpm = payload.get("rpm")
    status.speed_kmh = payload.get("speed_kmh")
    status.coolant_c = payload.get("coolant_c")
    status.dtc_stored = payload.get("dtc_stored") or []
    status.dtc_pending = payload.get("dtc_pending") or []
    if wifi_ssid:
        status.wifi_ssid = wifi_ssid
    status.raw_payload = payload
    status.updated_at = datetime.now(UTC)

    if payload.get("type") == "obd_snapshot":
        db.add(ObdSnapshot(scanner_id=scanner_id, payload=payload))

    await db.commit()


def effective_state(status: ScannerStatus | None) -> ScannerState:
    if status is None:
        return ScannerState.offline
    updated = status.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    age = datetime.now(UTC) - updated
    if age > timedelta(seconds=settings.scanner_offline_seconds):
        return ScannerState.offline
    return status.state


async def pair_user(db: AsyncSession, telegram_id: int, username: str | None, first_name: str | None, scanner_id: str) -> str:
    scanner = await db.get(Scanner, scanner_id)
    if scanner is None:
        return "Сканер не найден. Запусти мост на ПК — он зарегистрирует устройство при первом heartbeat."

    user = await db.get(TelegramUser, telegram_id)
    if user is None:
        user = TelegramUser(telegram_id=telegram_id)
        db.add(user)

    user.username = username
    user.first_name = first_name
    user.scanner_id = scanner_id
    await db.commit()
    return "ok"


async def save_cursor_key(db: AsyncSession, telegram_id: int, api_key: str) -> tuple[bool, str]:
    valid = await validate_cursor_api_key(api_key)
    user = await db.get(TelegramUser, telegram_id)
    if user is None:
        return False, "Сначала привяжи сканер: /start"

    user.cursor_key_enc = encrypt(api_key.strip()) if valid else None
    user.cursor_key_valid = valid
    await db.commit()
    if valid:
        return True, "Cursor API ключ принят."
    return False, "Ключ не прошёл проверку. Возьми ключ в Cursor Dashboard → Integrations."


async def get_user_context(db: AsyncSession, telegram_id: int) -> TelegramUser | None:
    result = await db.execute(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    return result.scalar_one_or_none()


def can_ecu_connected(status: ScannerStatus | None) -> bool:
    if status is None:
        return False
    payload = status.raw_payload or {}
    if payload.get("type") == "obd_error":
        return False
    if payload.get("type") == "obd_snapshot":
        return bool(payload.get("vin")) or payload.get("rpm") is not None
    return status.state == ScannerState.on_car


def blocks_from_payload(payload: dict[str, Any]) -> list[str]:
    blocks = payload.get("blocks")
    if isinstance(blocks, list):
        cleaned = [str(b).strip() for b in blocks if b]
        if cleaned:
            return cleaned[:8]
    out: list[str] = []
    if payload.get("vin"):
        out.append("ECU")
    if payload.get("rpm") is not None:
        out.append("Двигатель")
    return out


def format_obd_context(scanner_id: str, status: ScannerStatus | None, state: ScannerState) -> str:
    if status is None:
        return f"Сканер {scanner_id}: данных ещё не было."

    lines = [
        f"ID сканера: {scanner_id}",
        f"Состояние: {state.value} (online=связь с облаком есть, on_car=ECU ответила)",
        f"Обновлено: {status.updated_at.isoformat()}",
    ]
    if status.wifi_ssid:
        lines.append(f"Wi‑Fi: {status.wifi_ssid}")

    payload = status.raw_payload or {}
    msg_type = payload.get("type")

    if msg_type == "obd_error":
        lines.append("С ESP/CAN: ECU пока не отвечает на шину.")
        lines.append(f"Сообщение: {payload.get('message', 'unknown')}")
        if payload.get("hint"):
            lines.append(f"Hint: {payload['hint']}")
    elif msg_type == "obd_snapshot":
        lines.append(f"CAN bitrate: {payload.get('bitrate') or status.bitrate or '?'}")
        if payload.get("vin") or status.vin:
            lines.append(f"VIN: {payload.get('vin') or status.vin}")
        if payload.get("manufacturer") or status.manufacturer:
            lines.append(f"Марка (WMI): {payload.get('manufacturer') or status.manufacturer}")
        rpm = payload.get("rpm") if payload.get("rpm") is not None else status.rpm
        if rpm is not None:
            lines.append(
                f"Live: RPM={rpm}, speed={payload.get('speed_kmh', status.speed_kmh)} km/h, "
                f"coolant={payload.get('coolant_c', status.coolant_c)} °C"
            )
        stored = payload.get("dtc_stored") or status.dtc_stored or []
        pending = payload.get("dtc_pending") or status.dtc_pending or []
        lines.append(f"DTC stored: {', '.join(stored) if stored else 'нет'}")
        lines.append(f"DTC pending: {', '.join(pending) if pending else 'нет'}")
    else:
        lines.append(f"Сырой payload: {payload}")

    return "\n".join(lines)


async def ask_for_user(db: AsyncSession, telegram_id: int, question: str) -> str:
    user = await get_user_context(db, telegram_id)
    if user is None or not user.scanner_id:
        return "Сначала привяжи сканер (/start)."
    if not user.cursor_key_valid or not user.cursor_key_enc:
        return "Добавь Cursor API ключ: /cursor"

    status = await db.get(ScannerStatus, user.scanner_id)
    state = effective_state(status)
    if state == ScannerState.offline:
        return "Сканер offline — нет связи с облаком. Проверь Wi‑Fi на ESP или мост на ПК."

    obd_block = format_obd_context(user.scanner_id, status, state)

    prompt = f"""{SYSTEM_PROMPT}

--- Данные сканера (реальные, с VPS) ---
{obd_block}
--- конец данных ---

Вопрос пользователя: {question}
"""
    api_key = decrypt(user.cursor_key_enc)
    return await ask_cursor(api_key, prompt)


def _tg_html(text: str) -> str:
    return escape(str(text), quote=False)


def format_status(scanner_id: str, status: ScannerStatus | None) -> str:
    """Telegram HTML — ключ: значение в одной строке, эмоджi справа."""
    state = effective_state(status)
    state_lines = {
        ScannerState.offline: ("Не в сети", "⚫"),
        ScannerState.waiting: ("Активен, ожидание авто", "🟡"),
        ScannerState.on_car: ("Подключён к авто", "🟢"),
        ScannerState.error: ("Ошибка", "🔴"),
    }
    label, emoji = state_lines.get(state, (state.value, ""))
    lines: list[str] = [
        f"<b>Сканер #{_tg_html(scanner_id)}</b>",
        f"Статус: {_tg_html(label)}  {emoji}",
    ]

    if status is None or state == ScannerState.offline:
        return "\n\n".join(lines)

    if status.wifi_ssid:
        lines.append(f"Wi‑Fi: <code>{_tg_html(status.wifi_ssid)}</code>")

    payload = status.raw_payload or {}
    can_ok = can_ecu_connected(status)
    lines.append(f"CAN: {'✅' if can_ok else '❌'}")

    if can_ok:
        manufacturer = payload.get("manufacturer") or status.manufacturer
        vin = payload.get("vin") or status.vin
        if manufacturer:
            lines.append(f"Марка авто: {_tg_html(manufacturer)}")
        if vin:
            lines.append(f"VIN: <code>{_tg_html(vin)}</code>")
        block_list = blocks_from_payload(payload)
        if block_list:
            lines.append(f"Блоки: {_tg_html(', '.join(block_list))}")

    return "\n\n".join(lines)
