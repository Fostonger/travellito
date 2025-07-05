import logging
import os
from functools import lru_cache
import time
from datetime import datetime
import httpx
from jose import jwt

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.filters.callback_data import CallbackData
try:
    from aiogram.middleware.logging import LoggingMiddleware as _AiogramLoggingMiddleware
except ImportError:  # fallback for aiogram versions without built-in logging middleware
    class _AiogramLoggingMiddleware:  # type: ignore
        async def __call__(self, handler, event, data):
            return await handler(event, data)
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
#  Configuration helpers
# ---------------------------------------------------------------------------

load_dotenv()  # allow local development with a .env file


class Settings:
    """Application settings sourced from environment variables."""

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBHOOK_SECRET: str = os.getenv("BOT_WEBHOOK_SECRET", "")  # optional, use BOT_TOKEN if empty
    WEB_API: str = os.getenv("WEB_API", "http://web:8000")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "http://webapp:5173")  # Vite dev server default

    @property
    def webhook_path(self) -> str:
        return f"/webhook/{self.WEBHOOK_SECRET or self.BOT_TOKEN}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Identify which flavour of bot is running: 'tourist' (default) or 'manager'.
BOT_MODE = os.getenv("BOT_MODE", "tourist").lower()

if not settings.BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

# ---------------------------------------------------------------------------
#  aiogram setup
# ---------------------------------------------------------------------------

bot = Bot(settings.BOT_TOKEN, parse_mode="HTML")

storage = MemoryStorage()

dp = Dispatcher(storage=storage)
router = Router()

# Storage for user auth tokens
user_tokens = {}

# ---------------------------------------------------------------------------
#  Authentication helper
# ---------------------------------------------------------------------------

async def authenticate_user(user_id: int) -> dict:
    """Authenticate a user with the web API and store their tokens.
    
    This function will:
    1. Check if the user already has a valid token
    2. If token exists and is not close to expiry, return it
    3. If token doesn't exist or is close to expiry, get a new one
    4. Store the token for future use
    """
    logging.info(f"Starting authentication for user_id: {user_id}")
    
    # Check if user already has a token
    if user_id in user_tokens:
        token_data = user_tokens[user_id]
        
        # Check if token is about to expire (within 5 minutes)
        try:
            # Decode token without verification to check expiry
            payload = jwt.decode(token_data.get('access_token', ''), 
                                options={"verify_signature": False})
            exp = payload.get('exp', 0)
            now = int(time.time())
            
            # If token is valid for more than 5 minutes, reuse it
            if exp > now + 300:  # 5 minutes = 300 seconds
                logging.info(f"Using cached token for user_id: {user_id} (expires in {exp - now} seconds)")
                return token_data
            else:
                logging.info(f"Token for user_id: {user_id} is about to expire, refreshing")
        except Exception as e:
            logging.warning(f"Error checking token expiry: {str(e)}")
            # Continue to get a new token
    
    # Get user info from Telegram
    try:
        user = await bot.get_chat(user_id)
        logging.info(f"Got user from Telegram: {user.id}, {user.first_name}")
    except Exception as e:
        logging.exception(f"Error getting user from Telegram: {str(e)}")
        raise ValueError(f"Could not get user info from Telegram: {str(e)}")
    
    if not user:
        raise ValueError("Could not get user info from Telegram")
        
    # Convert to dict format expected by API
    user_data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
    }
    
    logging.info(f"Authenticating user: {user_data}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Call our auth endpoint
            auth_url = f"{settings.WEB_API}/api/v1/auth/telegram/bot"
            logging.info(f"Calling auth endpoint: {auth_url}")
            
            response = await client.post(
                auth_url,
                json=user_data,
                timeout=10
            )
            
            logging.info(f"Auth response status: {response.status_code}")
            
            if response.status_code != 200:
                logging.error(f"Auth error: {response.status_code} - {response.text}")
                return None
                
            tokens = response.json()
            logging.info(f"Authentication successful for user {user_id}. Token received: {tokens.get('access_token')[:10]}...")
            
            # Store tokens for this user
            user_tokens[user_id] = tokens
            return tokens
    except Exception as e:
        logging.exception(f"Authentication error: {str(e)}")
        return None

# Middlewares ----------------------------------------------------------------

# built-in logging middleware (requires python -m logging.basicConfig())
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

router.message.middleware(_AiogramLoggingMiddleware())

dp.include_router(router)


# Simple rate-limit middleware (per-user, in-memory) -------------------------
class RateLimitMiddleware:
    def __init__(self, limit: float = 1.0):
        self.limit = limit
        self._last: dict[int, float] = {}

    async def __call__(self, handler, event: Message, data):
        """Reject events that arrive sooner than <limit> seconds since the last one."""
        from time import monotonic

        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        uid = event.from_user.id
        now = monotonic()
        last = self._last.get(uid, 0)
        if now - last < self.limit:
            # Silently ignore the event to avoid spamming the bot.
            return
        self._last[uid] = now
        return await handler(event, data)


router.message.middleware(RateLimitMiddleware())


# Handlers -------------------------------------------------------------------

@router.message(F.text == "/start")
async def cmd_start(msg: Message):
    # Manager bot skips WebApp and only offers broadcast command
    if BOT_MODE == "manager":
        lang = _detect_lang(msg)
        await msg.answer(_("manager_greet", lang))
        return

    # Authenticate user first to ensure we have valid tokens
    tokens = None
    if msg.from_user:
        try:
            # This will automatically handle token expiry and refresh
            tokens = await authenticate_user(msg.from_user.id)
            logging.info(f"Got tokens for user {msg.from_user.id}: {tokens is not None}")
        except Exception as e:
            logging.warning(f"Authentication failed: {str(e)}")
            # Continue anyway - the webapp will handle auth if needed

    # Preserve the raw payload (after /start) – contains QR metadata like
    # `apt_<apartment_id>` which the WebApp will parse.
    args: str | None = None
    if msg.text and len(msg.text.split(maxsplit=1)) == 2:
        args = msg.text.split(maxsplit=1)[1]

    lang = _detect_lang(msg)
    launch_url = settings.WEBAPP_URL
    query_params = []
    
    if args:
        query_params.append(f"start={args}")
    
    query_params.append(f"lang={lang}")
    
    # Pass auth token to the webapp if available
    if tokens and tokens.get('access_token'):
        query_params.append(f"token={tokens['access_token']}")
    
    # Build the final URL with all query parameters
    if query_params:
        launch_url += f"?{'&'.join(query_params)}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("browse_btn", lang), web_app=WebAppInfo(url=launch_url))]
        ]
    )

    await msg.answer(_("greet", lang), reply_markup=kb)

# Handle deep links with start parameters
@router.message(lambda msg: msg.text and msg.text.startswith("/start "))
async def cmd_start_with_args(msg: Message):
    # Just forward to the main start handler
    await cmd_start(msg)


@router.message()
async def echo(msg: Message, state: FSMContext):
    """Default fallback – echoes only when the user is *not* in an active flow."""
    if await state.get_state() is None:
        await msg.answer(msg.text)


# ---------------------------------------------------------------------------
#  FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Travellito Telegram Bot", version="0.1.0")


@app.on_event("startup")
async def on_startup():
    logging.info("Starting up bot and FastAPI app…")


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
    logging.info("Bot session closed.")


# --- Telegram webhook endpoint ---------------------------------------------

@app.post(settings.webhook_path)
async def telegram_webhook(request: Request):
    """Receive incoming updates from Telegram and forward them to aiogram."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    update = Update.model_validate(body)
    await dp.feed_update(bot, update)
    return JSONResponse({"ok": True})


# --- Health check -----------------------------------------------------------

@app.get("/healthz", summary="Lightweight liveness probe")
async def healthz():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
#  Tour MANAGER – broadcast flow (Phase 4)
# ---------------------------------------------------------------------------

# Shared secret to mint service-to-service JWTs (must match web/ SECRET_KEY)
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    logging.warning("SECRET_KEY env var not set – bot cannot call protected API endpoints")

ALGORITHM = "HS256"


def _bot_jwt(ttl_seconds: int = 3600) -> str:
    """Return a short-lived service token with role = 'bot'."""
    payload = {
        "sub": "bot",  # synthetic user id
        "role": "bot",
        "exp": int(time.time()) + ttl_seconds,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class _DepCB(CallbackData, prefix="dep"):
    dep_id: int


class BroadcastStates(StatesGroup):
    choosing_dep = State()
    entering_msg = State()


@router.message(F.text == "/my_tours")
async def cmd_my_tours(msg: Message, state: FSMContext):
    """List upcoming departures so a manager can pick one to broadcast to."""
    if BOT_MODE != "manager":
        return

    if not SECRET_KEY:
        await msg.answer("❌ Internal error: server secret not configured.")
        return

    token = _bot_jwt()
    url = f"{settings.WEB_API}/api/v1/departures"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        except httpx.HTTPError as exc:
            logging.exception("Failed fetching departures: %s", exc)
            await msg.answer("⚠️ Could not fetch departures. Please try again later.")
            return

    if resp.status_code != 200:
        logging.error("Departures API error %s – %s", resp.status_code, resp.text)
        await msg.answer("⚠️ Could not fetch departures (server error).")
        return

    deps: list[dict] = resp.json()
    if not deps:
        await msg.answer("You have no upcoming departures with bookings.")
        return

    # Build inline keyboard (1 button per row)
    kb_rows: list[list[InlineKeyboardButton]] = []
    for d in deps:
        ts = d.get("starts_at")
        try:
            # Format ISO string nicely
            starts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
            ts_txt = starts_dt.strftime("%d %b %H:%M") if starts_dt else "TBA"
        except Exception:
            ts_txt = ts or "TBA"
        label = f"{d.get('tour_title', 'Tour')} – {ts_txt}"
        kb_rows.append([InlineKeyboardButton(text=label, callback_data=_DepCB(dep_id=d["id"]).pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await msg.answer("Select a departure to broadcast to:", reply_markup=kb)

    await state.set_state(BroadcastStates.choosing_dep)


@router.callback_query(_DepCB.filter(), BroadcastStates.choosing_dep)
async def on_dep_chosen(cb: CallbackQuery, callback_data: _DepCB, state: FSMContext):
    if BOT_MODE != "manager":
        return
    await cb.answer()  # ack to Telegram
    dep_id = callback_data.dep_id
    await state.update_data(dep_id=dep_id)
    await cb.message.edit_reply_markup()  # remove buttons to tidy chat
    await cb.message.answer(
        "Great! Now send the message you wish to broadcast to all tourists of this departure.\n"
        "You can send text up to 4096 characters.")
    await state.set_state(BroadcastStates.entering_msg)


@router.message(BroadcastStates.entering_msg)
async def on_broadcast_msg(msg: Message, state: FSMContext):
    if BOT_MODE != "manager":
        return
    data = await state.get_data()
    dep_id: int | None = data.get("dep_id")
    if dep_id is None:
        await msg.answer("❌ Unexpected error: missing departure ID.")
        await state.clear()
        return

    txt = msg.text or msg.caption  # If it's text message, caption for media
    if not txt:
        await msg.answer("⚠️ Please send a text message. Media broadcast not yet supported.")
        return

    if not SECRET_KEY:
        await msg.answer("❌ Internal error: server secret not configured.")
        await state.clear()
        return

    token = _bot_jwt()
    url = f"{settings.WEB_API}/api/v1/departures/{dep_id}/broadcast"

    payload = {"text": txt}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        except httpx.HTTPError as exc:
            logging.exception("Broadcast API call failed: %s", exc)
            await msg.answer("❌ Failed to schedule broadcast. Please try again later.")
            await state.clear()
            return

    if resp.status_code != 202:
        logging.error("Broadcast API error %s – %s", resp.status_code, resp.text)
        await msg.answer("❌ Server rejected broadcast: " + resp.text)
    else:
        await msg.answer("✅ Broadcast scheduled! Tourists will receive your message shortly.")

    await state.clear()


# ---------------------------------------------------------------------------
#  Basic i18n helper (ru / en)
# ---------------------------------------------------------------------------

# In-memory user preference.  For MVP we keep it simple; migrate to Redis/DB
# if persistence across restarts becomes important.
_user_lang_pref: dict[int, str] = {}

_MESSAGES = {
    "ru": {
        "greet": "👋 Привет! Нажмите кнопку ниже, чтобы посмотреть экскурсии.",
        "browse_btn": "🌍 Смотреть экскурсии",
        "manager_greet": "👋 Здравствуйте, менеджер! Используйте /my_tours для рассылки сообщений туристам.",
        "lang_prompt": "🌐 Выберите язык / Choose language",
        "lang_set": "✅ Язык переключён на {lang}",
    },
    "en": {
        "greet": "👋 Hi! Tap the button below to browse tours.",
        "browse_btn": "🌍 Browse Tours",
        "manager_greet": "👋 Hi Manager! Use /my_tours to send updates to your tourists.",
        "lang_prompt": "🌐 Choose your language",
        "lang_set": "✅ Language switched to {lang}",
    },
}


def _detect_lang(msg: "Message | CallbackQuery") -> str:
    """Return language code 'ru' or 'en' for *msg* with fallbacks."""
    uid = msg.from_user.id if msg.from_user else None  # type: ignore[attr-defined]
    # 1) Explicit preference
    if uid and uid in _user_lang_pref:
        return _user_lang_pref[uid]
    # 2) Telegram UI language (e.g. 'ru', 'en', 'en-US')
    code: str | None = msg.from_user.language_code if msg.from_user else None  # type: ignore[attr-defined]
    if code and code.lower().startswith("ru"):
        return "ru"
    return "en"


# Helper to pull a translated string
def _(key: str, lang: str) -> str:
    return _MESSAGES.get(lang, _MESSAGES["en"]).get(key, key)


# ---------------------------------------------------------------------------
#  Language selection command & callbacks
# ---------------------------------------------------------------------------

class LangCB(CallbackData, prefix="lang"):
    code: str  # 'ru' | 'en'


# /lang command -- lets a user override auto-detected language
@router.message(F.text == "/lang")
async def cmd_lang(msg: Message):
    lang = _detect_lang(msg)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Русский", callback_data=LangCB(code="ru").pack()),
                InlineKeyboardButton(text="English", callback_data=LangCB(code="en").pack()),
            ]
        ]
    )
    await msg.answer(_("lang_prompt", lang), reply_markup=kb)


@router.callback_query(LangCB.filter())
async def on_lang_cb(cb: CallbackQuery, callback_data: LangCB):
    _user_lang_pref[cb.from_user.id] = callback_data.code  # type: ignore[arg-type]
    # Confirmation alert (no message edit needed)
    text = _("lang_set", callback_data.code).format(
        lang="Русский" if callback_data.code == "ru" else "English"
    )
    await cb.answer(text, show_alert=True)
    # Optionally delete keyboard to reduce clutter
    try:
        await cb.message.edit_reply_markup(reply_markup=None)  # type: ignore[func-returns-value]
    except Exception:
        pass


        pass 


# TODO: remove this when before deploy
if __name__ == "__main__":
    import asyncio, logging
    from aiogram import executor

    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
# ────────────────────────────────────────────────────────