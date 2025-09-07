from __future__ import annotations

import logging
from decimal import Decimal
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from ..core.base import BaseService
from ..models import Purchase, TicketCategory, Departure, Tour, PurchaseItem, User, Apartment
from .telegram_service import TelegramService

logger = logging.getLogger(__name__)

# Default Russian template for booking confirmation
BOOKING_TEMPLATE = (
    "Вы успешно забронировали билеты на тур {tour_name} "
    "на общую сумму {total_price}:\n"
    "{items_block}\n"
    "Отправление {departure_datetime} от памятника Шаляпина, расположенного на улице Баумана\n"
    "Имейте в виду, что экскурсия проходит по воде, так что возьмите с собой дождевик.\n"
    "Приятного путешествия!"
)


class NotificationService(BaseService):
    """Domain notifications (Telegram, email, push…). Currently Telegram-only."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self._tg = TelegramService()  # Main bot for tourist notifications
        self._support_tg = TelegramService(bot_type="support")  # Support bot for admin notifications

    async def send_booking_confirmation(self, booking_id: int) -> None:
        """Send Telegram confirmation message for a freshly created booking.

        All needed relationships are eager-loaded to prevent implicit IO inside
        attribute access (which would otherwise raise `MissingGreenlet`).
        """
        from sqlalchemy.orm import selectinload

        stmt = (
            select(Purchase)
            .where(Purchase.id == booking_id)
            .options(
                selectinload(Purchase.user),
                selectinload(Purchase.items).selectinload(PurchaseItem.category),
                selectinload(Purchase.departure).selectinload(Departure.tour).selectinload(Tour.city),
            )
        )

        result = await self.session.execute(stmt)
        purchase: Purchase | None = result.scalar_one_or_none()
        if not purchase:
            logger.error("Purchase %s not found; cannot send notification", booking_id)
            return

        user: User | None = purchase.user
        if not user or not user.tg_id:
            logger.info("Booking %s user has no Telegram id; skipping notification", booking_id)
            return

        departure: Departure | None = purchase.departure
        tour: Tour | None = departure.tour if departure else None
        city = tour.city if tour else None

        # Build items breakdown
        items_block_lines: List[str] = []
        for item in purchase.items:
            cat = item.category
            cat_name = cat.name if cat else f"Категория {item.category_id}"
            items_block_lines.append(f"    {cat_name} — {item.qty}")
        items_block = "\n".join(items_block_lines)

        # Departure datetime adjusted for city timezone (if provided)
        from datetime import timedelta
        if departure:
            local_dt = departure.starts_at
            if city and city.timezone_offset_min is not None:
                local_dt = local_dt + timedelta(minutes=city.timezone_offset_min)
            
            # Format date in Russian style with month name
            russian_months = {
                1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
                7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
            }
            day = local_dt.day
            month = russian_months[local_dt.month]
            year = local_dt.year
            time = local_dt.strftime("%H:%M")
            dep_dt_str = f"{day} {month} {year}, {time}"
        else:
            dep_dt_str = "—"

        total_price = f"{Decimal(purchase.amount):.2f} ₽"
        tour_name = tour.title if tour else "(Неизвестный тур)"

        # Use tour's custom template if available, otherwise use default
        template = tour.booking_template if tour and tour.booking_template else BOOKING_TEMPLATE
        
        message_text = template.format(
            tour_name=tour_name,
            total_price=total_price,
            items_block=items_block,
            departure_datetime=dep_dt_str,
        )

        await self._tg.send_message(chat_id=user.tg_id, text=message_text)

        # Mark as notified
        purchase.tourist_notified = True
        purchase.status_changed_at = datetime.utcnow()
        await self.session.commit() 

    async def send_message_to_admin(self, admin_tg_id: int, text: str, reply_markup=None) -> None:
        """Send a message to an admin user via Telegram using the support bot.
        
        Args:
            admin_tg_id: Telegram ID of the admin
            text: Message text to send
            reply_markup: Optional inline keyboard markup
        """
        try:
            # Use the support bot instead of main bot
            await self._support_tg.send_message(
                chat_id=admin_tg_id,
                text=text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_tg_id}: {e}")
            raise

    async def notify_admins_new_booking(self, booking_id: int) -> None:
        """Notify all admin users about a new booking via Telegram.
        
        Args:
            booking_id: ID of the newly created booking
        """
        from sqlalchemy.orm import selectinload
        from sqlalchemy import and_
        
        # Get the booking with all needed relationships
        stmt = (
            select(Purchase)
            .where(Purchase.id == booking_id)
            .options(
                selectinload(Purchase.user),
                selectinload(Purchase.items).selectinload(PurchaseItem.category),
                selectinload(Purchase.departure).selectinload(Departure.tour).selectinload(Tour.city),
                selectinload(Purchase.apartment)
            )
        )
        
        result = await self.session.execute(stmt)
        purchase: Purchase | None = result.scalar_one_or_none()
        
        if not purchase:
            logger.error("Purchase %s not found; cannot notify admins", booking_id)
            return
        
        # Get all admin users with Telegram IDs
        admin_stmt = select(User).where(
            and_(
                User.role == "admin",
                User.tg_id.isnot(None)
            )
        )
        admins = await self.session.scalars(admin_stmt)
        
        # Build notification message
        user = purchase.user
        user_info = f"{user.first or ''} {user.last or ''} (@{user.username or 'no_username'})"
        
        departure = purchase.departure
        tour = departure.tour if departure else None
        tour_name = tour.title if tour else "Unknown Tour"
        city_name = tour.city.name if tour and tour.city else "Unknown City"
        
        # Format departure datetime
        departure_datetime = departure.starts_at.strftime("%d.%m.%Y %H:%M") if departure else "Unknown"
        
        # Build items breakdown
        items_text = []
        for item in purchase.items:
            cat = item.category
            cat_name = cat.name if cat else "Unknown Category"
            items_text.append(f"  • {cat_name}: {item.qty} шт. × {item.amount/item.qty:.2f} ₽")
        items_block = "\n".join(items_text) if items_text else "No items"
        
        # Check if booking is from apartment referral
        apartment_text = ""
        if purchase.apartment_id and purchase.apartment:
            apartment_text = f"\n🏠 <b>Источник:</b> Квартира #{purchase.apartment.id} ({purchase.apartment.name or 'Без названия'})"
        
        text = (
            f"🎫 <b>Новое бронирование</b>\n\n"
            f"<b>ID:</b> #{purchase.id}\n"
            f"<b>Пользователь:</b> {user_info}\n"
            f"<b>Телефон:</b> {user.phone or 'Не указан'}\n"
            f"<b>Тур:</b> {tour_name}\n"
            f"<b>Город:</b> {city_name}\n"
            f"<b>Отправление:</b> {departure_datetime}\n"
            f"<b>Статус:</b> {purchase.status}\n"
            f"<b>Сумма:</b> {purchase.amount} ₽\n"
            f"{apartment_text}\n\n"
            f"<b>Состав заказа:</b>\n{items_block}"
        )
        
        # Send to all admins
        for admin in admins:
            try:
                await self.send_message_to_admin(
                    admin_tg_id=admin.tg_id,
                    text=text
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin.id} about booking: {e}") 