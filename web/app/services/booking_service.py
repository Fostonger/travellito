from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal

from app.core import BaseService, NotFoundError, ValidationError, ConflictError, BusinessLogicError
from app.infrastructure.repositories import PurchaseRepository, DepartureRepository, TourRepository
from app.models import Purchase, Tour, Departure


class BookingService(BaseService):
    """Booking/Purchase service handling business logic"""
    
    def __init__(self, session, purchase_repo: Optional[PurchaseRepository] = None,
                 departure_repo: Optional[DepartureRepository] = None,
                 tour_repo: Optional[TourRepository] = None):
        super().__init__(session)
        self.purchase_repo = purchase_repo or PurchaseRepository(session)
        self.departure_repo = departure_repo or DepartureRepository(session)
        self.tour_repo = tour_repo or TourRepository(session)
    
    async def get_agency_bookings(
        self,
        agency_id: int,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Purchase]:
        """Get bookings for an agency with optional date filtering"""
        return await self.purchase_repo.get_by_agency(
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
        status: str
    ) -> Purchase:
        """Update booking status with validation"""
        
        # Validate status
        if status not in ["confirmed", "rejected"]:
            raise ValidationError("Invalid status. Must be 'confirmed' or 'rejected'", field="status")
        
        # Get booking with details
        booking = await self.purchase_repo.get_with_details(booking_id)
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
        updated_booking = await self.purchase_repo.update_status(
            booking_id,
            status,
            tourist_notified=False  # Will be set true when notification sent
        )
        
        # Mark as viewed
        await self.purchase_repo.mark_as_viewed(booking_id)
        
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
        pending_count = await self.purchase_repo.count_by_status(agency_id, "pending")
        confirmed_count = await self.purchase_repo.count_by_status(agency_id, "confirmed")
        rejected_count = await self.purchase_repo.count_by_status(agency_id, "rejected")
        total_count = pending_count + confirmed_count + rejected_count
        
        return {
            "total": total_count,
            "pending": pending_count,
            "confirmed": confirmed_count,
            "rejected": rejected_count
        } 