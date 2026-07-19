from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db
from app.models import ScannerStatus
from app.schemas import AskRequest, CursorKeyRequest, HeartbeatRequest, PairRequest
from app.services.scanner import (
    ask_for_user,
    format_status,
    get_user_context,
    pair_user,
    save_cursor_key,
    upsert_heartbeat,
)

router = APIRouter(prefix="/v1/bot", tags=["bot"])


def verify_bot_token(x_bot_token: str = Header(...)) -> None:
    if x_bot_token != settings.bot_internal_token:
        raise HTTPException(status_code=401, detail="invalid bot token")


@router.post("/pair")
async def bot_pair(body: PairRequest, db: AsyncSession = Depends(get_db), _: None = Depends(verify_bot_token)):
    msg = await pair_user(db, body.telegram_id, body.username, body.first_name, body.scanner_id)
    if msg != "ok":
        raise HTTPException(status_code=404, detail=msg)
    return {"ok": True}


@router.post("/cursor-key")
async def bot_cursor_key(
    body: CursorKeyRequest, db: AsyncSession = Depends(get_db), _: None = Depends(verify_bot_token)
):
    ok, msg = await save_cursor_key(db, body.telegram_id, body.api_key)
    return {"ok": ok, "message": msg}


@router.get("/status/{telegram_id}")
async def bot_status(telegram_id: int, db: AsyncSession = Depends(get_db), _: None = Depends(verify_bot_token)):
    user = await get_user_context(db, telegram_id)
    if user is None or not user.scanner_id:
        return {"text": "Сканер не привязан. /start", "ready": False}
    status = await db.get(ScannerStatus, user.scanner_id)
    return {"text": format_status(user.scanner_id, status), "ready": True}


@router.get("/session/{telegram_id}")
async def bot_session(telegram_id: int, db: AsyncSession = Depends(get_db), _: None = Depends(verify_bot_token)):
    """Reconnect: keep scanner + Cursor key, refresh status."""
    user = await get_user_context(db, telegram_id)
    if user is None or not user.scanner_id:
        return {
            "ready": False,
            "text": "Сессия пустая. Первый раз: /start\n(код сканера + Cursor API key)",
        }

    status = await db.get(ScannerStatus, user.scanner_id)
    status_text = format_status(user.scanner_id, status)
    cursor_line = "Cursor API: сохранён" if user.cursor_key_valid else "Cursor API: не задан — /cursor"

    text = (
        "Переподключено. Настройки на месте, заново вводить ничего не нужно.\n\n"
        f"Сканер: {user.scanner_id}\n"
        f"{cursor_line}\n\n"
        f"{status_text}"
    )
    return {"ready": True, "text": text, "scanner_id": user.scanner_id, "cursor_ok": user.cursor_key_valid}


@router.post("/ask")
async def bot_ask(body: AskRequest, db: AsyncSession = Depends(get_db), _: None = Depends(verify_bot_token)):
    try:
        answer = await ask_for_user(db, body.telegram_id, body.question)
        return {"text": answer}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
