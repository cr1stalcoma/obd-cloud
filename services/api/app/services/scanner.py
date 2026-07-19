from datetime import UTC, datetime, timedelta
from typing import Any

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.models import ObdSnapshot, Scanner, ScannerState, ScannerStatus, TelegramUser
from app.services.cursor import ask_cursor, validate_cursor_api_key

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SYSTEM_PROMPT = """Ты автомобильный диагност OBD-II. Отвечай на русском, кратко и по делу.
Используй только переданные данные сканера. Не выдумывай показания.
Если данных нет — так и скажи."""


def hash_secret(secret: str) -> str:
    return pwd_context.hash(secret)


def verify_secret(secret: str, secret_hash: str) -> bool:
    return pwd_context.verify(secret, secret_hash)


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
) -> None:
    scanner = await db.get(Scanner, scanner_id)
    if scanner is None:
        scanner = Scanner(id=scanner_id, secret_hash=hash_secret(secret))
        db.add(scanner)
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


async def ask_for_user(db: AsyncSession, telegram_id: int, question: str) -> str:
    user = await get_user_context(db, telegram_id)
    if user is None or not user.scanner_id:
        return "Сначала привяжи сканер (/start)."
    if not user.cursor_key_valid or not user.cursor_key_enc:
        return "Добавь Cursor API ключ: /cursor"

    status = await db.get(ScannerStatus, user.scanner_id)
    state = effective_state(status)
    if state == ScannerState.offline:
        return "Сканер offline. Запусти мост на ПК и подключи ESP."

    obd_block = "нет snapshot"
    if status and status.raw_payload:
        obd_block = str(status.raw_payload)

    prompt = f"""{SYSTEM_PROMPT}

Данные OBD snapshot:
{obd_block}

Состояние сканера: {state.value}

Вопрос пользователя:
{question}
"""
    api_key = decrypt(user.cursor_key_enc)
    return await ask_cursor(api_key, prompt)


def format_status(scanner_id: str, status: ScannerStatus | None) -> str:
    state = effective_state(status)
    icons = {
        ScannerState.offline: "⚫ offline",
        ScannerState.waiting: "🟡 включён, ждёт авто",
        ScannerState.on_car: "🟢 подключён к авто",
        ScannerState.error: "🔴 ошибка",
    }
    lines = [f"Сканер *{scanner_id}*", icons.get(state, state.value)]
    if status and state != ScannerState.offline:
        if status.vin:
            lines.append(f"VIN: `{status.vin}`")
        if status.manufacturer:
            lines.append(f"Марка (WMI): {status.manufacturer}")
        if status.rpm is not None:
            lines.append(f"RPM: {status.rpm} | speed: {status.speed_kmh} km/h | coolant: {status.coolant_c} °C")
        stored = status.dtc_stored or []
        pending = status.dtc_pending or []
        lines.append(f"DTC stored: {', '.join(stored) if stored else 'нет'}")
        lines.append(f"DTC pending: {', '.join(pending) if pending else 'нет'}")
        lines.append(f"CAN: {status.bitrate or '?'}")
        lines.append(f"Обновлено: {status.updated_at.isoformat()}")
    return "\n".join(lines)
