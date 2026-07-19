import httpx

from app.config import settings


class ApiClient:
    def __init__(self) -> None:
        self._headers = {"X-Bot-Token": settings.bot_internal_token}

    async def pair(self, telegram_id: int, username: str | None, first_name: str | None, scanner_id: str) -> dict:
        async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0) as client:
            response = await client.post(
                "/v1/bot/pair",
                json={
                    "telegram_id": telegram_id,
                    "username": username,
                    "first_name": first_name,
                    "scanner_id": scanner_id,
                },
                headers=self._headers,
            )
            if response.status_code == 404:
                return {"ok": False, "message": response.json().get("detail", "not found")}
            response.raise_for_status()
            return {"ok": True}

    async def set_cursor_key(self, telegram_id: int, api_key: str) -> dict:
        async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=60.0) as client:
            response = await client.post(
                "/v1/bot/cursor-key",
                json={"telegram_id": telegram_id, "api_key": api_key},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def status(self, telegram_id: int) -> str:
        async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0) as client:
            response = await client.get(f"/v1/bot/status/{telegram_id}", headers=self._headers)
            response.raise_for_status()
            return response.json()["text"]

    async def ask(self, telegram_id: int, question: str) -> str:
        async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=180.0) as client:
            response = await client.post(
                "/v1/bot/ask",
                json={"telegram_id": telegram_id, "question": question},
                headers=self._headers,
            )
            if response.status_code >= 400:
                detail = response.json().get("detail", "error")
                return f"Ошибка: {detail}"
            return response.json()["text"]
