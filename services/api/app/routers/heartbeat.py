from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import HeartbeatRequest
from app.services.scanner import upsert_heartbeat

router = APIRouter(prefix="/v1", tags=["scanner"])


@router.post("/heartbeat")
async def heartbeat(body: HeartbeatRequest, db: AsyncSession = Depends(get_db)):
    try:
        await upsert_heartbeat(db, body.scanner_id, body.secret, body.payload)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"ok": True}
