from __future__ import annotations

import os
import httpx
import logging
from typing import Optional


logger = logging.getLogger(__name__)


class TelegramService:
    """Lightweight async client for Telegram Bot API interactions."""

    def __init__(self, bot_token: Optional[str] = None) -> None:
        self.bot_token = bot_token or os.getenv("BOT_TOKEN")
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN environment variable is required for TelegramService")
        self._api_base = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a plaintext message to a user.

        Args:
            chat_id: Telegram chat id (int)
            text: Message body (Markdown & HTML are allowed by Telegram but keep plain for now)
        """
        if not chat_id:
            logger.warning("Attempted to send Telegram message with empty chat_id; skipping")
            return
        async with httpx.AsyncClient() as client:
            try:
                await client.post(f"{self._api_base}/sendMessage", json={"chat_id": chat_id, "text": text})
            except Exception as exc:
                logger.exception("Failed to send Telegram message: %s", exc) 