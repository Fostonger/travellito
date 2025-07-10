from datetime import date, datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from typing import List, Dict, Any, Optional

from app.core import BaseError
from app.models import Purchase, User, Departure, Tour, PurchaseItem, TicketCategory
from app.infrastructure.repositories.purchase_repository import PurchaseRepository


class BookingService:
    def __init__(self, session):
        self.session = session
        self.repository = PurchaseRepository(session)

    async def export_bookings(
        self, 
        agency_id: int, 
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        format: str = "json"
    ) -> List[Dict[str, Any]]:
        """Export bookings with optional date filtering"""
        return await self.repository.export_bookings(
            agency_id=agency_id,
            from_date=from_date,
            to_date=to_date
        )

    async def get_booking_metrics(self, agency_id: int) -> Dict[str, Any]:
        """Get booking metrics for agency dashboard"""
        return await self.repository.get_booking_metrics(agency_id)

    async def update_booking_status(self, booking_id: int, agency_id: int, status: str) -> Purchase:
        """Update booking status (confirm or reject)"""
        if status not in ["confirmed", "rejected"]:
            raise BaseError("Invalid status. Must be 'confirmed' or 'rejected'")

        # Get booking with tour agency check
        booking = await self.repository.get_booking_with_agency_check(booking_id, agency_id)
        
        if not booking:
            raise BaseError("Booking not found or not associated with your agency", status_code=404)
        
        # Update status
        booking.status = status
        booking.status_changed_at = datetime.utcnow()
        
        return booking
        
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
            if booking.status == "pending":
                tour = booking.departure.tour
                cutoff_time = booking.departure.starts_at - timedelta(hours=tour.free_cancellation_cutoff_h)
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
                "items": items_data
            })
        
        # Sort by departure date, with upcoming tours first
        output.sort(key=lambda x: x["departure_date"])
        
        return output
    
    async def cancel_tourist_booking(self, booking_id: int, user_id: int) -> bool:
        """Cancel a booking for a tourist user"""
        # Get the booking
        stmt = (
            select(Purchase)
            .join(Departure, Purchase.departure_id == Departure.id)
            .join(Tour, Departure.tour_id == Tour.id)
            .where(
                Purchase.id == booking_id,
                Purchase.user_id == user_id
            )
            .options(joinedload(Purchase.departure).joinedload(Departure.tour))
        )
        
        result = await self.session.execute(stmt)
        booking = result.scalars().first()
        
        if not booking:
            raise BaseError("Booking not found", status_code=404)
        
        if booking.status != "pending":
            raise BaseError("Only pending bookings can be cancelled", status_code=400)
        
        # Check cancellation policy
        now = datetime.utcnow()
        tour = booking.departure.tour
        cutoff_time = booking.departure.starts_at - timedelta(hours=tour.free_cancellation_cutoff_h)
        
        if now >= cutoff_time:
            raise BaseError(
                f"Free cancellation is only available {tour.free_cancellation_cutoff_h} hours before departure",
                status_code=400
            )
        
        # Cancel the booking
        booking.status = "cancelled"
        booking.status_changed_at = datetime.utcnow()
        
        return True 