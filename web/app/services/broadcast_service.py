"""Broadcast service for messaging operations."""

from __future__ import annotations

import os
import asyncio
from typing import List, Dict, Any, Sequence
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ValidationError, AuthorizationError
from ..models import Purchase, User, Departure, Tour

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var must be set for broadcast")


class BroadcastService(BaseService):
    """Service for broadcast operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.bot_token = BOT_TOKEN
    
    async def list_departures_for_broadcast(
        self, user_role: str, agency_id: int | None = None
    ) -> List[Dict[str, Any]]:
        """List upcoming departures with bookings for broadcast.
        
        Args:
            user_role: User role (admin, bot, manager)
            agency_id: Agency ID for manager filtering
            
        Returns:
            List of departure dictionaries
        """
        now = datetime.now(timezone.utc)
        
        # Base query: departures in the future with bookings > 0
        stmt = (
            select(Departure.id, Tour.title, Departure.starts_at)
            .join(Tour, Tour.id == Departure.tour_id)
            .join(Purchase, Purchase.departure_id == Departure.id)
            .where(Departure.starts_at >= now)
            .group_by(Departure.id, Tour.title, Departure.starts_at)
            .order_by(Departure.starts_at.asc())
        )
        
        # Restrict to manager's agency if needed
        if user_role == "manager" and agency_id is not None:
            stmt = stmt.where(Tour.agency_id == agency_id)
        
        rows = await self.session.execute(stmt)
        
        return [
            {
                "id": d_id,
                "tour_title": title,
                "starts_at": starts,
            }
            for d_id, title, starts in rows
        ]
    
    async def validate_broadcast_permission(
        self, departure_id: int, user_id: int, user_role: str
    ) -> None:
        """Validate user has permission to broadcast to departure.
        
        Args:
            departure_id: Departure ID
            user_id: User ID
            user_role: User role
            
        Raises:
            NotFoundError: If departure not found
            ForbiddenError: If user lacks permission
        """
        if user_role in ["admin", "bot"]:
            return  # Always allowed
        
        if user_role == "manager":
            # Fetch departure & related tour
            dep: Departure | None = await self.session.get(Departure, departure_id)
            if not dep:
                raise NotFoundError("Departure not found")
            
            tour: Tour | None = await self.session.get(Tour, dep.tour_id)
            if not tour:
                raise NotFoundError("Tour not found")
            
            manager: User | None = await self.session.get(User, user_id)
            if not manager or manager.agency_id is None or manager.agency_id != tour.agency_id:
                raise AuthorizationError("Not allowed for this departure")
    
    async def get_chat_ids_for_departure(self, departure_id: int) -> List[int]:
        """Get Telegram chat IDs for tourists booked on a departure.
        
        Args:
            departure_id: Departure ID
            
        Returns:
            List of Telegram chat IDs
        """
        # Use a new session to avoid interfering with the main transaction
        async with AsyncSession() as sess:
            stmt = (
                select(User.tg_id)
                .join(Purchase, Purchase.user_id == User.id)
                .where(Purchase.departure_id == departure_id)
            )
            result = await sess.scalars(stmt)
            chat_ids: Sequence[int] = list(result)
        
        return list(chat_ids)
    
    async def send_broadcast(
        self,
        chat_ids: List[int],
        text: str | None = None,
        photo_url: str | None = None,
        document_url: str | None = None,
    ) -> None:
        """Send broadcast message to Telegram users.
        
        Args:
            chat_ids: List of Telegram chat IDs
            text: Text message
            photo_url: Photo URL
            document_url: Document URL
        """
        if not chat_ids:
            return
        
        api = f"https://api.telegram.org/bot{self.bot_token}"
        
        async with httpx.AsyncClient() as client:
            rate_limit = 25  # msgs per second (Telegram limit 30)
            
            async def _send(chat_id: int):
                if text:
                    await client.post(
                        f"{api}/sendMessage",
                        json={"chat_id": chat_id, "text": text}
                    )
                if photo_url:
                    await client.post(
                        f"{api}/sendPhoto",
                        json={"chat_id": chat_id, "photo": photo_url}
                    )
                if document_url:
                    await client.post(
                        f"{api}/sendDocument",
                        json={"chat_id": chat_id, "document": document_url}
                    )
            
            # Send sequentially obeying rate-limit
            for i, cid in enumerate(chat_ids):
                await _send(cid)
                if (i + 1) % rate_limit == 0:
                    await asyncio.sleep(1) 