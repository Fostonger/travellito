from datetime import date, datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from typing import List, Dict, Any, Optional

from app.core import BaseError
from app.core import BaseService, NotFoundError, ValidationError, ConflictError, BusinessLogicError
from app.models import Purchase, User, Departure, Tour, PurchaseItem, TicketCategory
from app.infrastructure.repositories.purchase_repository import PurchaseRepository
from app.infrastructure.metrika import track_async_event


class BookingService:
    def __init__(self, session):
        self.session = session
        self.repository = PurchaseRepository(session)

    async def get_agency_bookings(
        self,
        agency_id: int,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Purchase]:
        """Get bookings for an agency with optional date filtering"""
        return await self.repository.get_by_agency(
            agency_id,
            from_date=from_date,
            to_date=to_date,
            skip=skip,
            limit=limit
        )
    
    async def update_booking_status(
        self,
        booking_id: int,
        agency_id: int,
        status: str,
        client_id: Optional[str] = None
    ) -> Purchase:
        """Update booking status with validation"""
        
        # Validate status
        if status not in ["confirmed", "rejected"]:
            raise ValidationError("Invalid status. Must be 'confirmed' or 'rejected'", field="status")
        
        # Get booking with details
        booking = await self.repository.get_with_details(booking_id)
        if not booking:
            raise NotFoundError("Booking", booking_id)
        
        # Verify agency ownership
        if booking.departure.tour.agency_id != agency_id:
            raise NotFoundError("Booking", booking_id)
        
        # Check if already processed
        if booking.status != "pending":
            raise BusinessLogicError(
                f"Booking already {booking.status}",
                rule="booking_status_transition"
            )
        
        # Update status
        updated_booking = await self.repository.update_status(
            booking_id,
            status,
            tourist_notified=False  # Will be set true when notification sent
        )
        
        # Mark as viewed
        await self.repository.mark_as_viewed(booking_id)
        
        # Track event in analytics
        if client_id:
            track_async_event(
                client_id=client_id,
                action=f"booking_{status}",
                ec="booking",  # event category
                el=str(booking_id),  # event label
                tour_id=str(booking.departure.tour_id),
                amount=str(booking.total_amount)
            )
        
        return updated_booking

    async def export_bookings(
        self, 
        agency_id: int, 
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        format: str = "json"
    ) -> List[Dict[str, Any]]:
        """Export bookings in specified format"""
        
        # Get bookings
        bookings = await self.get_agency_bookings(
            agency_id,
            from_date=from_date,
            to_date=to_date,
            skip=0,
            limit=1000  # Reasonable limit for exports
        )
        
        # Format data for export
        export_data = []
        for booking in bookings:
            # Build category breakdown
            categories = []
            for item in booking.items:
                categories.append({
                    "name": item.category.name,
                    "quantity": item.qty,
                    "amount": float(item.amount)
                })
            
            export_data.append({
                "booking_id": booking.id,
                "booking_date": booking.ts.isoformat(),
                "tour_title": booking.departure.tour.title,
                "departure_date": booking.departure.starts_at.isoformat(),
                "customer_name": f"{booking.user.first or ''} {booking.user.last or ''}".strip() or "Unknown",
                "customer_phone": booking.user.phone or "",
                "total_quantity": booking.qty,
                "total_amount": float(booking.amount),
                "status": booking.status,
                "viewed": booking.viewed,
                "categories": categories
            })
        
        return export_data

    async def get_booking_metrics(self, agency_id: int) -> Dict[str, Any]:
        """Get booking metrics for agency dashboard"""
        
        # Count bookings by status
        pending_count = await self.repository.count_by_status(agency_id, "pending")
        confirmed_count = await self.repository.count_by_status(agency_id, "confirmed")
        rejected_count = await self.repository.count_by_status(agency_id, "rejected")
        total_count = pending_count + confirmed_count + rejected_count
        
        return {
            "total": total_count,
            "pending": pending_count,
            "confirmed": confirmed_count,
            "rejected": rejected_count
        }
        
    async def get_tourist_bookings(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all bookings for a tourist user, sorted by departure date"""
        # Query to get bookings with related tour and departure info
        stmt = (
            select(Purchase)
            .join(Departure, Purchase.departure_id == Departure.id)
            .join(Tour, Departure.tour_id == Tour.id)
            .where(Purchase.user_id == user_id)
            .options(
                joinedload(Purchase.departure).joinedload(Departure.tour),
                joinedload(Purchase.items).joinedload(PurchaseItem.category)
            )
            .order_by(Departure.starts_at)
        )
        
        result = await self.session.execute(stmt)
        bookings = result.scalars().unique().all()
        
        # Format the results
        now = datetime.utcnow()
        output = []
        
        for booking in bookings:
            # Check if booking is cancellable (based on departure time and tour's cancellation policy)
            is_cancellable = False
            # Allow cancellation for both pending and confirmed bookings
            if booking.status in ["pending"]:
                cutoff_time = booking.departure.starts_at
                is_cancellable = now < cutoff_time
            
            # Format items
            items_data = []
            for item in booking.items:
                items_data.append({
                    "category_name": item.category.name,
                    "qty": item.qty,
                    "amount": float(item.amount)
                })
            
            output.append({
                "id": booking.id,
                "amount": float(booking.amount),
                "status": booking.status,
                "created": booking.ts,
                "departure_date": booking.departure.starts_at,
                "tour_title": booking.departure.tour.title,
                "tour_id": booking.departure.tour.id,
                "departure_id": booking.departure.id,
                "is_cancellable": is_cancellable,
                "items": items_data,
                "tour_address": booking.departure.tour.address
            })
        
        # Sort by departure date, with upcoming tours first
        output.sort(key=lambda x: x["departure_date"])
        
        return output
    
    async def cancel_tourist_booking(
        self, 
        booking_id: int, 
        user_id: int, 
        client_id: Optional[str] = None
    ) -> bool:
        """Cancel a booking as a tourist"""
        # Find the booking
        booking = await self.repository.get_with_details(booking_id)
        if not booking:
            raise NotFoundError("Booking", booking_id)
        
        # Check ownership
        if booking.user_id != user_id:
            raise NotFoundError("Booking", booking_id)
        
        # Check if cancellable
        now = datetime.utcnow()
        cutoff = booking.departure.starts_at - timedelta(hours=booking.departure.tour.free_cancellation_cutoff_h)
        
        if now >= cutoff:
            raise BusinessLogicError(
                "Booking can't be cancelled within the cutoff period",
                rule="booking_cancellation"
            )
        
        # Cancel the booking
        result = await self.repository.update_status(booking_id, "cancelled")
        
        # Track event in analytics
        if client_id:
            track_async_event(
                client_id=client_id,
                action="booking_cancelled",
                value=1,
                ec="booking",
                el=str(booking_id),
                tour_id=str(booking.departure.tour_id),
                amount=str(booking.total_amount),
                time_to_departure=str((booking.departure.starts_at - now).total_seconds() // 3600)  # hours
            )
        
        return bool(result) 