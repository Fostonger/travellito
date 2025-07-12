from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import BaseRepository
from app.models import Departure, Tour, Purchase


class DepartureRepository(BaseRepository[Departure]):
    """Departure repository implementation"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Departure, session)
    
    async def get_by_tour(
        self,
        tour_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        from_date: Optional[datetime] = None
    ) -> List[Departure]:
        """Get departures for a specific tour"""
        query = select(Departure).where(Departure.tour_id == tour_id)
        
        if from_date:
            query = query.where(Departure.starts_at >= from_date)
        
        query = query.order_by(Departure.starts_at).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_by_agency(
        self,
        agency_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        tour_id: Optional[int] = None
    ) -> List[Departure]:
        """Get departures for an agency's tours"""
        query = (
            select(Departure)
            .join(Tour, Departure.tour_id == Tour.id)
            .where(Tour.agency_id == agency_id)
        )
        
        if tour_id:
            query = query.where(Departure.tour_id == tour_id)
        
        query = query.order_by(Departure.starts_at).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_with_tour(self, departure_id: int) -> Optional[Departure]:
        """Get departure with tour loaded"""
        query = (
            select(Departure)
            .options(selectinload(Departure.tour))
            .where(Departure.id == departure_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_seats_taken(self, departure_id: int) -> int:
        """Get number of seats taken for a departure"""
        stmt = (
            select(func.coalesce(func.sum(Purchase.qty), 0))
            .where(
                Purchase.departure_id == departure_id,
                Purchase.status.in_(["pending", "confirmed"])  # Only count active bookings
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def get_available_capacity(self, departure_id: int) -> Optional[int]:
        """Get available capacity for a departure"""
        departure = await self.get(departure_id)
        if not departure:
            return None
        
        taken = await self.get_seats_taken(departure_id)
        return departure.capacity - taken
    
    async def get_modifiable_before_cutoff(self) -> List[Departure]:
        """Get departures that are still modifiable but past their cutoff"""
        query = (
            select(Departure)
            .join(Tour)
            .where(Departure.modifiable == True)
            .options(selectinload(Departure.tour))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def lock_for_update(self, departure_id: int) -> Optional[Departure]:
        """Get departure with exclusive lock for updates"""
        query = (
            select(Departure)
            .where(Departure.id == departure_id)
            .with_for_update()
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() 