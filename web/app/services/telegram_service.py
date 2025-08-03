from __future__ import annotations

import os
import httpx
import logging
from typing import Optional, Dict, Any


logger = logging.getLogger(__name__)


class TelegramService:
    """Lightweight async client for Telegram Bot API interactions."""

    def __init__(self, bot_token: Optional[str] = None, bot_type: str = "main") -> None:
        """Initialize Telegram service with specified bot token.
        
        Args:
            bot_token: Optional explicit token. If not provided, will use environment variable
            bot_type: Which bot to use - 'main' or 'support'
        """
        # Select the appropriate env var based on bot type
        env_var = "SUPPORT_BOT_TOKEN" if bot_type == "support" else "BOT_TOKEN"
        
        self.bot_token = bot_token or os.getenv(env_var)
        if not self.bot_token:
            raise RuntimeError(f"{env_var} environment variable is required for TelegramService")
        
        self._api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self.bot_type = bot_type

    async def send_message(self, chat_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None) -> None:
        """Send a plaintext message to a user.

        Args:
            chat_id: Telegram chat id (int)
            text: Message body (Markdown & HTML are allowed by Telegram but keep plain for now)
            reply_markup: Optional inline keyboard markup or other Telegram reply options
        """
        if not chat_id:
            logger.warning("Attempted to send Telegram message with empty chat_id; skipping")
            return
            
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        # Add reply_markup if provided
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        async with httpx.AsyncClient() as client:
            try:
                await client.post(f"{self._api_base}/sendMessage", json=payload)
            except Exception as exc:
                logger.exception("Failed to send Telegram message: %s", exc) 