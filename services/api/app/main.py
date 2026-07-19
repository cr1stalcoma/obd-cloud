import logging

from fastapi import FastAPI

from app.routers import bot, heartbeat

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="OBD Cloud API", version="0.1.0")
app.include_router(heartbeat.router)
app.include_router(bot.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
