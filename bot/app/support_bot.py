import logging
import os
from functools import lru_cache
import httpx
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters.callback_data import CallbackData
from aiogram.filters import Command, CommandObject
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
#  Configuration
# ---------------------------------------------------------------------------

load_dotenv()


class Settings:
    """Application settings for support bot."""
    
    SUPPORT_BOT_TOKEN: str = os.getenv("SUPPORT_BOT_TOKEN", "")
    WEBHOOK_SECRET: str = os.getenv("SUPPORT_BOT_WEBHOOK_SECRET", "")
    WEB_API: str = os.getenv("WEB_API", "http://web:8000")
    
    @property
    def webhook_path(self) -> str:
        """Generate webhook path from bot token or custom secret."""
        secret = self.WEBHOOK_SECRET or self.SUPPORT_BOT_TOKEN
        if not secret:
            raise ValueError("No bot token or webhook secret provided")
        return f"/support-webhook/{secret[-10:]}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

if not settings.SUPPORT_BOT_TOKEN:
    raise RuntimeError("SUPPORT_BOT_TOKEN environment variable is required")

# ---------------------------------------------------------------------------
#  Bot setup
# ---------------------------------------------------------------------------

bot = Bot(settings.SUPPORT_BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  FSM States
# ---------------------------------------------------------------------------

class SupportStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_admin_response = State()  # New state for waiting for admin response text


# ---------------------------------------------------------------------------
#  Callback data
# ---------------------------------------------------------------------------

class AdminActionCallback(CallbackData, prefix="admin"):
    action: str  # reply, complete_payment
    message_id: int


# ---------------------------------------------------------------------------
#  API Client for backend
# ---------------------------------------------------------------------------

class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        
    async def authenticate_user(self, tg_user: dict) -> dict:
        """Authenticate Telegram user and get auth token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/auth/telegram-auth",
                json={"telegram_user": tg_user}
            )
            response.raise_for_status()
            return response.json()
    
    async def create_support_message(self, token: str, message_type: str, message: str) -> dict:
        """Create a support message."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/support/messages",
                json={
                    "message_type": message_type,
                    "message": message
                },
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_admin_users(self) -> list:
        """Get all admin users with Telegram IDs."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/internal/admin-telegram-ids"
            )
            response.raise_for_status()
            return response.json()
    
    async def respond_to_message(self, token: str, message_id: int, response: str, mark_resolved: bool = False) -> dict:
        """Admin responds to a support message."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/support/messages/{message_id}/respond",
                json={
                    "response": response,
                    "mark_resolved": mark_resolved
                },
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def process_payment_request(self, token: str, request_id: int, status: str = "completed") -> dict:
        """Process a payment request."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/support/payment-requests/{request_id}/process",
                json={"status": status},
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json()


backend = BackendClient(settings.WEB_API)
dp.include_router(router)

# Store user tokens
user_tokens = {}


# ---------------------------------------------------------------------------
#  Handlers
# ---------------------------------------------------------------------------

@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext):
    """Start command - show welcome message and options."""
    await state.clear()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="support_question")],
        [InlineKeyboardButton(text="⚠️ Сообщить о проблеме", callback_data="support_issue")]
    ])
    
    await msg.answer(
        "👋 Добро пожаловать в службу поддержки Travellito!\n\n"
        "Я помогу вам решить любые вопросы, связанные с нашим сервисом.\n\n"
        "Выберите, что вы хотите сделать:",
        reply_markup=keyboard
    )


@router.callback_query(F.data.in_(["support_question", "support_issue"]))
async def handle_support_type(callback: CallbackQuery, state: FSMContext):
    """Handle support type selection."""
    support_type = "question" if callback.data == "support_question" else "issue"
    
    await state.update_data(support_type=support_type)
    await state.set_state(SupportStates.waiting_for_message)
    
    prompt = (
        "❓ Пожалуйста, опишите ваш вопрос:" 
        if support_type == "question" 
        else "⚠️ Пожалуйста, опишите проблему, с которой вы столкнулись:"
    )
    
    await callback.message.edit_text(prompt)
    await callback.answer()


@router.message(SupportStates.waiting_for_message)
async def handle_support_message(msg: Message, state: FSMContext):
    """Handle the actual support message from user."""
    data = await state.get_data()
    support_type = data.get("support_type", "question")
    
    # Authenticate user
    try:
        tg_user = {
            "id": msg.from_user.id,
            "first_name": msg.from_user.first_name,
            "last_name": msg.from_user.last_name,
            "username": msg.from_user.username,
        }
        
        auth_result = await backend.authenticate_user(tg_user)
        token = auth_result["access_token"]
        user_tokens[msg.from_user.id] = token
        
        # Create support message
        result = await backend.create_support_message(
            token=token,
            message_type=support_type,
            message=msg.text
        )
        
        await msg.answer(
            "✅ Ваше сообщение успешно отправлено!\n\n"
            f"Номер обращения: #{result['id']}\n\n"
            "Наша служба поддержки свяжется с вами в ближайшее время. "
            "Обычно мы отвечаем в течение 1-2 часов в рабочее время."
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating support message: {e}")
        await msg.answer(
            "❌ Произошла ошибка при отправке сообщения. "
            "Пожалуйста, попробуйте позже или свяжитесь с нами напрямую."
        )
        await state.clear()


# Admin command handlers

# Add a more general message handler to catch commands that start with /reply
@router.message(lambda message: message.text and message.text.startswith('/reply'))
async def cmd_reply_general(msg: Message, state: FSMContext):
    """Handle reply commands with any format: /reply, /reply123, etc."""
    logger.info(f"Reply command received: {msg.text}")
    
    try:
        # Extract the message ID from the command
        command_text = msg.text.strip()
        message_id = None
        response_text = None
        
        # If the command is longer than "/reply", try to extract the ID
        if len(command_text) > 6:  # "/reply" is 6 chars
            # Try to extract message_id from /reply123
            command_parts = command_text[6:].strip().split(maxsplit=1)
            try:
                message_id = int(command_parts[0])
                if len(command_parts) > 1:
                    response_text = command_parts[1]
            except (ValueError, IndexError):
                logger.error(f"Failed to parse message ID from command: {command_text}")
                await msg.answer("Использование: /reply<ID> <ваш ответ> или /reply <ID> <ваш ответ>")
                return
        else:
            # Just "/reply" without args
            await msg.answer("Использование: /reply<ID> <ваш ответ> или /reply <ID> <ваш ответ>")
            return
        
        logger.info(f"Extracted message_id: {message_id}, response_text: {response_text}")
        
        # If we have message_id but no response text, store the ID and wait for response
        if not response_text:
            # Store message_id in state
            await state.update_data(reply_to_message_id=message_id)
            await state.set_state(SupportStates.waiting_for_admin_response)
            
            await msg.answer(f"Введите текст ответа на сообщение #{message_id}:")
            return
        
        # If we have both message_id and response, send immediately
        tg_user = {
            "id": msg.from_user.id,
            "first_name": msg.from_user.first_name,
            "last_name": msg.from_user.last_name,
            "username": msg.from_user.username,
        }
        
        auth_result = await backend.authenticate_user(tg_user)
        token = auth_result["access_token"]
        
        # Send response
        await backend.respond_to_message(
            token=token,
            message_id=message_id,
            response=response_text,
            mark_resolved=True
        )
        
        await msg.answer(f"✅ Ответ на сообщение #{message_id} успешно отправлен!")
        
    except Exception as e:
        logger.error(f"Error replying to message: {e}", exc_info=True)
        await msg.answer(f"❌ Ошибка при обработке команды: {str(e)}")


@router.message(SupportStates.waiting_for_admin_response)
async def handle_admin_response(msg: Message, state: FSMContext):
    """Handle admin response text after the /reply command."""
    try:
        # Get the message_id from state
        data = await state.get_data()
        message_id = data.get("reply_to_message_id")
        
        if not message_id:
            await msg.answer("❌ Ошибка: ID сообщения не найден")
            await state.clear()
            return
        
        response_text = msg.text
        if not response_text:
            await msg.answer("Пожалуйста, введите текст ответа")
            return
        
        # Get admin token
        tg_user = {
            "id": msg.from_user.id,
            "first_name": msg.from_user.first_name,
            "last_name": msg.from_user.last_name,
            "username": msg.from_user.username,
        }
        
        auth_result = await backend.authenticate_user(tg_user)
        token = auth_result["access_token"]
        
        # Send response
        await backend.respond_to_message(
            token=token,
            message_id=message_id,
            response=response_text,
            mark_resolved=True
        )
        
        await msg.answer(f"✅ Ответ на сообщение #{message_id} успешно отправлен!")
        
        # Clear state
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing admin response: {e}")
        await msg.answer("❌ Ошибка при отправке ответа")
        await state.clear()


@router.callback_query(AdminActionCallback.filter(F.action == "complete_payment"))
async def handle_complete_payment(callback: CallbackQuery, callback_data: AdminActionCallback):
    """Handle payment completion by admin."""
    try:
        # Get admin token
        tg_user = {
            "id": callback.from_user.id,
            "first_name": callback.from_user.first_name,
            "last_name": callback.from_user.last_name,
            "username": callback.from_user.username,
        }
        
        auth_result = await backend.authenticate_user(tg_user)
        token = auth_result["access_token"]
        
        # Process payment
        await backend.process_payment_request(
            token=token,
            request_id=callback_data.message_id,
            status="completed"
        )
        
        # Update message
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Выплата обработана</b>",
            reply_markup=None
        )
        
        await callback.answer("Выплата успешно обработана!")
        
    except Exception as e:
        logger.error(f"Error processing payment: {e}")
        await callback.answer("❌ Ошибка при обработке выплаты", show_alert=True)


# ---------------------------------------------------------------------------
#  FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Travellito Support Bot", version="0.1.0")


@app.on_event("startup")
async def on_startup():
    webhook_url = os.getenv("SUPPORT_BOT_WEBHOOK_URL", "")
    if webhook_url:
        await bot.set_webhook(webhook_url + settings.webhook_path)
        logger.info(f"Support bot webhook set to: {webhook_url}{settings.webhook_path}")


@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
    logger.info("Support bot session closed.")


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


@app.get("/healthz", summary="Lightweight liveness probe")
async def healthz():
    return {"status": "ok"} 