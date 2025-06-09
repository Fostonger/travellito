import asyncio, os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

BOT_TOKEN  = os.getenv("BOT_TOKEN")
PANEL_URL  = os.getenv("PANEL_URL", "https://example.com/login")

dp = Dispatcher()

@dp.message(F.text == "/start")
async def start(msg: Message):
    await msg.answer(f"Hi! Manage me here → {PANEL_URL}")

async def main():
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())