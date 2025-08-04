from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from sqlalchemy.orm import selectinload
from datetime import datetime

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ValidationError
from ..models import (
    User, Landlord, Purchase, Apartment, Tour, Departure,
    SupportMessage, SupportResponse, LandlordPaymentRequest,
    LandlordPaymentHistory
)
from .notification_service import NotificationService

logger = logging.getLogger(__name__)


class SupportService(BaseService):
    """Service for support system operations including messages and payment requests."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.notification_service = NotificationService(session)
    
    # Support Message Methods
    
    async def create_support_message(
        self,
        user_id: int,
        message_type: str,
        message: str
    ) -> SupportMessage:
        """Create a new support message and notify admins.
        
        Args:
            user_id: User ID who created the message
            message_type: Type of message (issue, question, payment_request)
            message: The message content
            
        Returns:
            Created SupportMessage
        """
        if message_type not in ["issue", "question", "payment_request"]:
            raise ValidationError("Invalid message type")
        
        # Ensure user_id is an integer
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            raise ValidationError("User ID must be an integer")
        
        support_msg = SupportMessage(
            user_id=user_id,
            message_type=message_type,
            message=message,
        )
        self.session.add(support_msg)
        await self.session.commit()
        
        # Notify all admin users
        await self._notify_admins_new_message(support_msg)
        
        return support_msg
    
    async def get_support_message(self, message_id: int) -> SupportMessage:
        """Get a support message by ID with all relationships loaded."""
        stmt = (
            select(SupportMessage)
            .where(SupportMessage.id == message_id)
            .options(
                selectinload(SupportMessage.user),
                selectinload(SupportMessage.assigned_admin),
                selectinload(SupportMessage.responses).selectinload(SupportResponse.admin)
            )
        )
        result = await self.session.execute(stmt)
        message = result.scalar_one_or_none()
        
        if not message:
            raise NotFoundError("Support message not found")
        
        return message
    
    async def list_support_messages(
        self,
        status: Optional[str] = None,
        message_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[SupportMessage]:
        """List support messages with optional filters."""
        stmt = select(SupportMessage).options(
            selectinload(SupportMessage.user),
            selectinload(SupportMessage.assigned_admin)
        )
        
        if status:
            stmt = stmt.where(SupportMessage.status == status)
        if message_type:
            stmt = stmt.where(SupportMessage.message_type == message_type)
            
        stmt = stmt.order_by(SupportMessage.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def assign_support_message(
        self,
        message_id: int,
        admin_id: int
    ) -> SupportMessage:
        """Assign a support message to an admin."""
        message = await self.get_support_message(message_id)
        
        message.assigned_admin_id = admin_id
        message.status = "in_progress"
        
        await self.session.commit()
        return message
    
    async def respond_to_support_message(
        self,
        message_id: int,
        admin_id: int,
        response_text: str,
        mark_resolved: bool = False
    ) -> SupportResponse:
        """Create a response to a support message and notify the user."""
        message = await self.get_support_message(message_id)
        
        # Create response
        response = SupportResponse(
            support_message_id=message_id,
            admin_id=admin_id,
            response=response_text
        )
        self.session.add(response)
        
        # Update message status if needed
        if mark_resolved:
            message.status = "resolved"

            # If this is a payment_request message, also complete the payment request entity
            if message.message_type == "payment_request":
                from ..models import Landlord, LandlordPaymentRequest
                # Find landlord linked to this support message
                landlord = await self.session.scalar(select(Landlord).where(Landlord.user_id == message.user_id))
                if landlord:
                    pending_req = await self.session.scalar(
                        select(LandlordPaymentRequest)
                        .where(
                            LandlordPaymentRequest.landlord_id == landlord.id,
                            LandlordPaymentRequest.status == "pending"
                        )
                        .order_by(LandlordPaymentRequest.requested_at.desc())
                        .limit(1)
                    )
                    if pending_req:
                        # Reuse existing logic to process the request
                        await self.process_payment_request(pending_req.id, admin_id, status="completed")
        elif message.status == "pending":
            message.status = "in_progress"
            message.assigned_admin_id = admin_id
        
        await self.session.commit()
        
        # Notify the user
        await self._notify_user_response(message, response_text)
        
        return response
    
    # Payment Request Methods
    
    async def can_request_payment(self, landlord_id: int) -> Dict[str, Any]:
        """Check if a landlord can request payment and return the details.
        
        Returns dict with:
            - can_request: bool
            - reason: str (if can't request)
            - available_amount: Decimal
            - unique_users_count: int
            - has_payment_info: bool
        """
        # Get landlord with payment info
        stmt = select(Landlord).where(Landlord.id == landlord_id)
        landlord = await self.session.scalar(stmt)
        
        if not landlord:
            raise NotFoundError("Landlord not found")
        
        # Check payment info
        has_payment_info = bool(landlord.phone_number and landlord.bank_name)
        
        # Get unique users count and calculate available amount
        stats = await self._get_landlord_payment_stats(landlord_id)
        
        unique_users_count = stats["unique_users_count"]
        total_earned = stats["total_earned"]
        total_paid = stats["total_paid"]
        available_amount = Decimal(str(round((total_earned - total_paid), 2)))
        
        # Determine if can request
        can_request = True
        reason = ""
        
        if not has_payment_info:
            can_request = False
            reason = "Не заполнены платежные реквизиты"
        elif unique_users_count < 1:
            can_request = False
            reason = f"Недостаточно уникальных пользователей ({unique_users_count}/10)"
        elif available_amount <= 0:
            can_request = False
            reason = "Нет доступных средств для вывода"
        
        # Check for pending requests
        pending_stmt = select(LandlordPaymentRequest).where(
            and_(
                LandlordPaymentRequest.landlord_id == landlord_id,
                LandlordPaymentRequest.status == "pending"
            )
        )
        pending_request = await self.session.scalar(pending_stmt)
        
        if pending_request:
            can_request = False
            reason = "У вас уже есть активная заявка на выплату"
        
        return {
            "can_request": can_request,
            "reason": reason,
            "available_amount": available_amount,
            "unique_users_count": unique_users_count,
            "has_payment_info": has_payment_info,
            "pending_request": pending_request is not None
        }
    
    async def create_payment_request(self, landlord_id: int) -> LandlordPaymentRequest:
        """Create a payment request for a landlord."""
        # Check if can request
        check_result = await self.can_request_payment(landlord_id)
        
        if not check_result["can_request"]:
            raise ValidationError(check_result["reason"])
        
        # Get landlord for payment info
        stmt = select(Landlord).where(Landlord.id == landlord_id)
        landlord = await self.session.scalar(stmt)
        
        # Create payment request
        payment_request = LandlordPaymentRequest(
            landlord_id=landlord_id,
            amount=check_result["available_amount"],
            phone_number=landlord.phone_number,
            bank_name=landlord.bank_name,
            unique_users_count=check_result["unique_users_count"]
        )
        self.session.add(payment_request)
        await self.session.commit()
        
        # Create support message for admins
        support_message = await self.create_support_message(
            user_id=landlord.user_id,
            message_type="payment_request",
            message=f"Запрос на выплату {payment_request.amount} ₽\nТелефон: {payment_request.phone_number}\nБанк: {payment_request.bank_name or 'Не указан'}"
        )
        
        return payment_request
    
    async def process_payment_request(
        self,
        request_id: int,
        admin_id: int,
        status: str = "completed"
    ) -> LandlordPaymentRequest:
        """Process a payment request."""
        if status not in ["completed", "rejected"]:
            raise ValidationError("Invalid status")
        
        # Get payment request
        stmt = (
            select(LandlordPaymentRequest)
            .where(LandlordPaymentRequest.id == request_id)
            .options(selectinload(LandlordPaymentRequest.landlord))
        )
        payment_request = await self.session.scalar(stmt)
        
        if not payment_request:
            raise NotFoundError("Payment request not found")
        
        if payment_request.status != "pending":
            raise ValidationError("Payment request is not pending")
        
        # Update request
        payment_request.status = status
        payment_request.processed_at = datetime.utcnow()
        payment_request.processed_by_id = admin_id
        
        # If completed, create payment history entry
        if status == "completed":
            payment_history = LandlordPaymentHistory(
                landlord_id=payment_request.landlord_id,
                amount=payment_request.amount,
                paid_by_id=admin_id,
                payment_request_id=request_id
            )
            self.session.add(payment_history)

            # Also mark related support messages as resolved
            await self.session.execute(
                update(SupportMessage)
                .where(
                    SupportMessage.user_id == payment_request.landlord.user_id,
                    SupportMessage.message_type == "payment_request",
                    SupportMessage.status == "pending"
                )
                .values(status="resolved")
            )
        
        await self.session.commit()
        
        # Notify landlord
        await self._notify_landlord_payment_status(payment_request)
        
        return payment_request
    
    async def get_landlord_balance_info(self, landlord_id: int) -> Dict[str, Any]:
        """Get balance information for landlord dashboard."""
        stats = await self._get_landlord_payment_stats(landlord_id)
        
        # Check for pending payment request
        pending_stmt = select(LandlordPaymentRequest).where(
            and_(
                LandlordPaymentRequest.landlord_id == landlord_id,
                LandlordPaymentRequest.status.in_(["pending", "processing"])
            )
        ).order_by(LandlordPaymentRequest.requested_at.desc()).limit(1)
        
        pending_request = await self.session.scalar(pending_stmt)
        
        return {
            "total_earned": stats["total_earned"],
            "total_paid": stats["total_paid"],
            "available_balance": stats["total_earned"] - stats["total_paid"],
            "unique_users_count": stats["unique_users_count"],
            "pending_request": pending_request
        }
    
    # Private helper methods
    
    async def _get_landlord_payment_stats(self, landlord_id: int) -> Dict[str, Any]:
        """Get payment statistics for a landlord."""
        # Get apartment IDs
        stmt_apartments = select(Apartment.id).where(Apartment.landlord_id == landlord_id)
        apartment_ids = [row[0] for row in await self.session.execute(stmt_apartments)]
        
        if not apartment_ids:
            return {
                "unique_users_count": 0,
                "total_earned": Decimal("0"),
                "total_paid": Decimal("0")
            }
        
        # Count unique users from apartments
        unique_users_stmt = (
            select(func.count(func.distinct(Purchase.user_id)))
            .where(
                and_(
                    Purchase.apartment_id.in_(apartment_ids),
                    Purchase.status == "confirmed"
                )
            )
        )
        unique_users_count = await self.session.scalar(unique_users_stmt) or 0
        
        # Calculate total earned from confirmed purchases
        earnings_stmt = (
            select(
                func.coalesce(
                    func.sum(Purchase.amount * Tour.max_commission_pct / 100),
                    0
                )
            )
            .join(Departure, Purchase.departure_id == Departure.id)
            .join(Tour, Departure.tour_id == Tour.id)
            .where(
                and_(
                    Purchase.apartment_id.in_(apartment_ids),
                    Purchase.status == "confirmed"
                )
            )
        )
        total_earned = await self.session.scalar(earnings_stmt) or Decimal("0")
        
        # Get total paid
        paid_stmt = (
            select(func.coalesce(func.sum(LandlordPaymentHistory.amount), 0))
            .where(LandlordPaymentHistory.landlord_id == landlord_id)
        )
        total_paid = await self.session.scalar(paid_stmt) or Decimal("0")
        
        return {
            "unique_users_count": unique_users_count,
            "total_earned": Decimal(str(total_earned)),
            "total_paid": Decimal(str(total_paid))
        }
    
    async def _notify_admins_new_message(self, message: SupportMessage) -> None:
        """Notify all admin users about a new support message."""
        # Get all admin users with Telegram IDs
        stmt = select(User).where(
            and_(
                User.role == "admin",
                User.tg_id.isnot(None)
            )
        )
        admins = await self.session.scalars(stmt)
        
        # Get user who created the message
        user = await self.session.get(User, message.user_id)
        user_info = f"{user.first or ''} {user.last or ''} (@{user.username or 'no_username'})"
        
        # Format message based on type
        if message.message_type == "payment_request":
            # Extract payment request ID from the support message
            # The message format includes the request details
            text = (
                f"💰 <b>Новый запрос на выплату</b>\n\n"
                f"От: {user_info}\n"
                f"Сообщение:\n{message.message}\n\n"
                f"ID сообщения: #{message.id}"
            )
            
            # For payment requests, we need to add a button to process it
            # Get the latest payment request for this user
            from ..models import LandlordPaymentRequest, Landlord
            landlord_stmt = select(Landlord).where(Landlord.user_id == user.id)
            landlord = await self.session.scalar(landlord_stmt)
            
            if landlord:
                request_stmt = (
                    select(LandlordPaymentRequest)
                    .where(
                        and_(
                            LandlordPaymentRequest.landlord_id == landlord.id,
                            LandlordPaymentRequest.status == "pending"
                        )
                    )
                    .order_by(LandlordPaymentRequest.requested_at.desc())
                    .limit(1)
                )
                payment_request = await self.session.scalar(request_stmt)
                
                if payment_request:
                    # Create keyboard dict directly instead of using aiogram types
                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "✅ Обработать выплату",
                                    "callback_data": f"admin:complete_payment:{payment_request.id}"
                                }
                            ]
                        ]
                    }
                    
                    # Send with keyboard
                    for admin in admins:
                        try:
                            await self.notification_service.send_message_to_admin(
                                admin_tg_id=admin.tg_id,
                                text=text,
                                reply_markup=keyboard
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin.id}: {e}")
                    return
        else:
            type_emoji = "❓" if message.message_type == "question" else "⚠️"
            type_text = "Вопрос" if message.message_type == "question" else "Проблема"
            
            text = (
                f"{type_emoji} <b>Новое сообщение в поддержку</b>\n\n"
                f"Тип: {type_text}\n"
                f"От: {user_info}\n"
                f"Сообщение:\n{message.message}\n\n"
                f"Для ответа используйте /reply{message.id}"
            )
        
        # Send to all admins without keyboard
        for admin in admins:
            try:
                await self.notification_service.send_message_to_admin(
                    admin_tg_id=admin.tg_id,
                    text=text
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin.id}: {e}")
    
    async def _notify_user_response(self, message: SupportMessage, response_text: str) -> None:
        """Notify user about admin response."""
        user = await self.session.get(User, message.user_id)
        
        if not user or not user.tg_id:
            logger.warning(f"Cannot notify user {message.user_id} - no Telegram ID")
            return
        
        text = (
            f"📬 <b>Ответ от службы поддержки</b>\n\n"
            f"На ваше сообщение:\n<i>{message.message[:100]}{'...' if len(message.message) > 100 else ''}</i>\n\n"
            f"Ответ:\n{response_text}"
        )
        
        try:
            await self.notification_service._support_tg.send_message(
                chat_id=user.tg_id,
                text=text
            )
        except Exception as e:
            logger.error(f"Failed to notify user {user.id}: {e}")
    
    async def _notify_landlord_payment_status(self, payment_request: LandlordPaymentRequest) -> None:
        """Notify landlord about payment request status change."""
        landlord = payment_request.landlord
        
        if not landlord.user_id:
            return
        
        user = await self.session.get(User, landlord.user_id)
        
        if not user or not user.tg_id:
            return
        
        if payment_request.status == "completed":
            text = (
                f"✅ <b>Ваш запрос на выплату обработан</b>\n\n"
                f"Сумма: {payment_request.amount} ₽\n"
                f"Статус: Выполнен\n\n"
                f"Средства будут переведены на указанные реквизиты в течение 1-2 рабочих дней."
            )
        else:
            text = (
                f"❌ <b>Ваш запрос на выплату отклонен</b>\n\n"
                f"Сумма: {payment_request.amount} ₽\n"
                f"Статус: Отклонен\n\n"
                f"Пожалуйста, свяжитесь с поддержкой для уточнения деталей."
            )
        
        try:
            await self.notification_service._tg.send_message(
                chat_id=user.tg_id,
                text=text
            )
        except Exception as e:
            logger.error(f"Failed to notify landlord {landlord.id}: {e}") 