import asyncio
import logging

logger = logging.getLogger(__name__)


def _validate_sync(api_key: str) -> bool:
    api_key = api_key.strip()
    if len(api_key) < 16:
        return False
    try:
        from cursor_sdk import Cursor

        models = Cursor.models.list(api_key=api_key)
        return len(models) > 0
    except Exception:
        logger.exception("cursor validate sync")
        return False


def _ask_sync(api_key: str, prompt: str) -> str:
    from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    from cursor_sdk.types import ModelParameterValue, ModelSelection

    result = Agent.prompt(
        prompt,
        AgentOptions(
            api_key=api_key.strip(),
            model=ModelSelection(
                id="composer-2.5",
                params=[ModelParameterValue(id="fast", value="true")],
            ),
            local=LocalAgentOptions(cwd="/tmp"),
        ),
    )
    if result.result:
        text = str(result.result)
        # Composer loves markdown; Telegram plain text reads better
        return text.replace("**", "").replace("__", "")
    return f"Статус: {result.status}"


async def validate_cursor_api_key(api_key: str) -> bool:
    return await asyncio.to_thread(_validate_sync, api_key)


async def ask_cursor(api_key: str, prompt: str) -> str:
    return await asyncio.to_thread(_ask_sync, api_key, prompt)
