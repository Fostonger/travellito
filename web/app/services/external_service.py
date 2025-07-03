"""External service for API key authenticated operations."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Sequence, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ValidationError, ConflictError
from ..models import Departure, Tour, Purchase, ApiKey


class ExternalService(BaseService):
    """Service for external API operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
    
    async def update_departure_capacity(
        self, agency_id: int, departure_id: int, capacity: int
    ) -> Dict[str, Any]:
        """Update departure capacity for an agency.
        
        Args:
            agency_id: Agency ID from API key
            departure_id: Departure ID
            capacity: New capacity
            
        Returns:
            Dict with departure ID and new capacity
            
        Raises:
            NotFoundError: If departure not found or doesn't belong to agency
            ConflictError: If new capacity is below booked seats
        """
        # Lock departure row
        stmt_dep = select(Departure).where(Departure.id == departure_id).with_for_update()
        dep: Departure | None = await self.session.scalar(stmt_dep)
        if not dep:
            raise NotFoundError("Departure not found")
        
        tour: Tour | None = await self.session.get(Tour, dep.tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Departure not found")
        
        # Check capacity against bookings
        taken_stmt = select(Purchase.qty).where(Purchase.departure_id == dep.id)
        taken_rows: Sequence[int] = (await self.session.scalars(taken_stmt)).all()
        taken = sum(taken_rows) if taken_rows else 0
        
        if capacity < taken:
            raise ConflictError("Capacity lower than booked seats")
        
        dep.capacity = capacity
        await self.session.commit()
        
        return {"id": dep.id, "capacity": dep.capacity}
    
    async def export_bookings(
        self,
        agency_id: int,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> List[Dict[str, Any]]:
        """Export bookings for an agency.
        
        Args:
            agency_id: Agency ID from API key
            from_date: Start date filter
            to_date: End date filter
            
        Returns:
            List of booking dictionaries
        """
        stmt = (
            select(
                Purchase.id,
                Purchase.ts,
                Purchase.qty,
                Purchase.amount,
                Purchase.amount_gross,
                Purchase.commission_pct,
                Departure.id.label("dep_id"),
                Departure.starts_at,
                Tour.title,
            )
            .join(Departure, Departure.id == Purchase.departure_id)
            .join(Tour, Tour.id == Departure.tour_id)
            .where(Tour.agency_id == agency_id)
            .order_by(Purchase.ts.desc())
        )
        
        # Date filters
        if from_date:
            stmt = stmt.where(
                Purchase.ts >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
            )
        if to_date:
            stmt = stmt.where(
                Purchase.ts <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc)
            )
        
        rows = (await self.session.execute(stmt)).all()
        
        bookings = []
        for bid, ts, qty, amount, amount_gross, pct, dep_id, starts, title in rows:
            bookings.append({
                "booking_id": bid,
                "departure_id": dep_id,
                "starts_at": starts.isoformat() if starts else None,
                "tour_title": title,
                "qty": qty,
                "net_price": str(amount),
            })
        
        return bookings 