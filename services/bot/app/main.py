import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from app.api_client import ApiClient
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api = ApiClient()


class Onboarding(StatesGroup):
    scanner_id = State()
    cursor_key = State()


async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.set_state(Onboarding.scanner_id)
    await message.answer(
        "OBD Cloud Scanner\n\n"
        "1) Введи код сканера (например 565300)\n"
        "2) Затем добавь Cursor API key\n\n"
        "Команды:\n"
        "/status — статус сканера\n"
        "/cursor — сменить Cursor API key\n"
        "/ask <вопрос> — спросить ИИ по данным OBD"
    )


async def on_scanner_id(message: Message, state: FSMContext) -> None:
    scanner_id = (message.text or "").strip()
    if not scanner_id.isdigit() or len(scanner_id) < 4:
        await message.answer("Код сканера — цифры, минимум 4 символа. Пример: 565300")
        return

    result = await api.pair(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        scanner_id,
    )
    if not result.get("ok"):
        await message.answer(result.get("message", "Не удалось привязать сканер."))
        return

    await state.update_data(scanner_id=scanner_id)
    await state.set_state(Onboarding.cursor_key)
    await message.answer(
        f"Сканер {scanner_id} привязан.\n\n"
        "Теперь отправь Cursor API key (сообщение будет удалено).\n"
        "Ключ: Cursor Dashboard → Integrations"
    )


async def on_cursor_key(message: Message, state: FSMContext) -> None:
    api_key = (message.text or "").strip()
    try:
        await message.delete()
    except Exception:
        pass

    wait = await message.answer("Проверяю ключ Cursor…")
    result = await api.set_cursor_key(message.from_user.id, api_key)
    await state.clear()

    if result.get("ok"):
        status = await api.status(message.from_user.id)
        await wait.edit_text(f"{result.get('message')}\n\n{status}", parse_mode="Markdown")
    else:
        await wait.edit_text(result.get("message", "Ключ не принят."))


async def cmd_status(message: Message) -> None:
    text = await api.status(message.from_user.id)
    await message.answer(text, parse_mode="Markdown")


async def cmd_cursor(message: Message, state: FSMContext) -> None:
    await state.set_state(Onboarding.cursor_key)
    await message.answer("Отправь новый Cursor API key (сообщение удалю после получения).")


async def cmd_ask(message: Message) -> None:
    question = (message.text or "").replace("/ask", "", 1).strip()
    if len(question) < 2:
        await message.answer("Пример: /ask Что значит P0420?")
        return
    wait = await message.answer("Думаю…")
    answer = await api.ask(message.from_user.id, question)
    if len(answer) > 4000:
        answer = answer[:3990] + "…"
    await wait.edit_text(answer)


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_cursor, Command("cursor"))
    dp.message.register(cmd_ask, Command("ask"))
    dp.message.register(on_scanner_id, Onboarding.scanner_id)
    dp.message.register(on_cursor_key, Onboarding.cursor_key)
    dp.message.register(cmd_ask, F.text.startswith("/ask "))

    logger.info("bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
