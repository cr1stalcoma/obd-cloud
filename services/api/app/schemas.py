from typing import Any

from pydantic import BaseModel, Field


class HeartbeatRequest(BaseModel):
    scanner_id: str = Field(min_length=3, max_length=32)
    secret: str = Field(min_length=8, max_length=128)
    payload: dict[str, Any]


class PairRequest(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    scanner_id: str


class CursorKeyRequest(BaseModel):
    telegram_id: int
    api_key: str


class AskRequest(BaseModel):
    telegram_id: int
    question: str = Field(min_length=2, max_length=4000)
