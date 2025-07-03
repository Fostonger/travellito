from typing import Optional, List, Dict, Any
from datetime import datetime, date
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import BaseRepository
from app.models import Purchase, Departure, Tour, User, PurchaseItem


class PurchaseRepository(BaseRepository[Purchase]):
    """Purchase/Booking repository implementation"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Purchase, session)
    
    async def get_by_departure(
        self,
        departure_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Purchase]:
        """Get purchases for a specific departure"""
        query = (
            select(Purchase)
            .where(Purchase.departure_id == departure_id)
            .order_by(Purchase.ts.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_by_user(
        self,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Purchase]:
        """Get purchases by user"""
        query = (
            select(Purchase)
            .where(Purchase.user_id == user_id)
            .order_by(Purchase.ts.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_by_agency(
        self,
        agency_id: int,
        *,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Purchase]:
        """Get purchases for an agency's tours"""
        query = (
            select(Purchase)
            .join(Departure)
            .join(Tour)
            .where(Tour.agency_id == agency_id)
            .options(
                selectinload(Purchase.user),
                selectinload(Purchase.departure).selectinload(Departure.tour),
                selectinload(Purchase.items).selectinload(PurchaseItem.category)
            )
        )
        
        if from_date:
            query = query.where(Purchase.ts >= from_date)
        if to_date:
            # Add one day to include the entire to_date
            query = query.where(Purchase.ts < datetime.combine(to_date, datetime.min.time()).replace(day=to_date.day + 1))
        
        query = query.order_by(Purchase.ts.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().unique().all())
    
    async def get_with_details(self, purchase_id: int) -> Optional[Purchase]:
        """Get purchase with all related data loaded"""
        query = (
            select(Purchase)
            .options(
                selectinload(Purchase.user),
                selectinload(Purchase.departure).selectinload(Departure.tour),
                selectinload(Purchase.items).selectinload(PurchaseItem.category)
            )
            .where(Purchase.id == purchase_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def update_status(
        self,
        purchase_id: int,
        status: str,
        tourist_notified: bool = False
    ) -> Optional[Purchase]:
        """Update purchase status"""
        purchase = await self.get(purchase_id)
        if not purchase:
            return None
        
        purchase.status = status
        purchase.status_changed_at = datetime.utcnow()
        purchase.tourist_notified = tourist_notified
        
        await self.session.flush()
        return purchase
    
    async def mark_as_viewed(self, purchase_id: int) -> Optional[Purchase]:
        """Mark purchase as viewed by agency"""
        purchase = await self.get(purchase_id)
        if not purchase:
            return None
        
        purchase.viewed = True
        await self.session.flush()
        return purchase
    
    async def count_by_status(
        self,
        agency_id: int,
        status: Optional[str] = None
    ) -> int:
        """Count purchases by status for an agency"""
        query = (
            select(func.count())
            .select_from(Purchase)
            .join(Departure)
            .join(Tour)
            .where(Tour.agency_id == agency_id)
        )
        
        if status:
            query = query.where(Purchase.status == status)
        
        result = await self.session.execute(query)
        return result.scalar() or 0 