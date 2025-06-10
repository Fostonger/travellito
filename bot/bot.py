import asyncio, os, textwrap
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, InputMediaPhoto
)
from aiogram.filters.callback_data import CallbackData
import aiohttp

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE  = os.getenv("WEB_API", "http://web:8000")

class TourCB(CallbackData, prefix="tour"):
    tid: int

dp = Dispatcher()
router = Router()
dp.include_router(router)

# ---------- /start handler with optional referral ----------
@router.message(F.text.startswith("/start"))
async def start(msg: Message):
    parts = msg.text.split()
    if len(parts) > 1 and parts[1].startswith("ref_"):
        landlord_id = parts[1].split("_")[1]
        async with aiohttp.ClientSession() as cli:
            await cli.post(f"{API_BASE}/referral",
                           json={"user_id": msg.from_user.id,
                                 "landlord_id": landlord_id})
    await list_tours(msg)

# ---------- List tours ----------
async def list_tours(msg: Message):
    async with aiohttp.ClientSession() as cli:
        tours = await (await cli.get(f"{API_BASE}/tours")).json()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=t["title"],
                callback_data=TourCB(tid=t["id"]).pack()   # pack() serialises → str
            )] for t in tours
        ]
    )
    await msg.answer("Available tours:", reply_markup=kb)

# ---------- Show tour details ----------
@router.callback_query(TourCB.filter())          # filter routes only tour callbacks
async def show_tour(call: CallbackQuery, callback_data: TourCB):
    tid = callback_data.tid
    async with aiohttp.ClientSession() as cli:
        tour = await (await cli.get(f"{API_BASE}/tours/{tid}")).json()
    media = [InputMediaPhoto(url) for url in tour["images"]] or None
    desc = textwrap.shorten(tour["description"], 1024)
    if media:
        await call.message.answer_media_group(media)
    await call.message.answer(
        f"*{tour['title']}*\n\n{desc}\n\nPrice: {tour['price']}€",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="Buy",
                    callback_data=f"buy_{tid}")
            ]]),
        parse_mode="Markdown"
    )
    await call.answer()

# ---------- Buy flow ----------
@router.callback_query(F.data.startswith("buy_"))
async def buy_tour(call: CallbackQuery):
    tid = int(call.data.split("_")[1])
    # create Stripe checkout session via API
    async with aiohttp.ClientSession() as cli:
        r = await cli.post(f"{API_BASE}/buy", json={
            "tour_id": tid,
            "user_id": call.from_user.id
        })
    url = (await r.json())["checkout_url"]
    await call.answer()          # close loading
    await call.message.answer(f"Pay here 👉 {url}")

# ---------- run ----------
async def main():
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
