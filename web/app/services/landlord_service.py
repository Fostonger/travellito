"""Landlord service for landlord operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ValidationError
from ..models import (
    Apartment, Landlord, Purchase, Tour, LandlordCommission,
    TicketCategory, Referral
)
from ..infrastructure.repositories import UserRepository, TourRepository


class LandlordService(BaseService):
    """Service for landlord operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.user_repository = UserRepository(session)
        self.tour_repository = TourRepository(session)

    # User Management

    async def get_landlord_by_user_id(self, user_id: int) -> Landlord:
        """Get landlord by user ID.
        
        Args:
            user_id: User ID
            
        Returns:
            Landlord object
            
        Raises:
            NotFoundError: If landlord not found
        """
        stmt = select(Landlord).where(Landlord.user_id == user_id)
        landlord = await self.session.scalar(stmt)
        
        if not landlord:
            raise NotFoundError(f"Landlord not found for user ID {user_id}")
        
        return landlord

    # Apartment Management
    
    async def list_apartments(
        self, landlord_id: int, limit: int = 50, offset: int = 0
    ) -> List[Apartment]:
        """List apartments for a landlord.
        
        Args:
            landlord_id: Landlord ID
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of Apartment objects
        """
        stmt = (
            select(Apartment)
            .where(Apartment.landlord_id == landlord_id)
            .order_by(Apartment.id)
            .limit(limit)
            .offset(offset)
        )
        apartments = await self.session.scalars(stmt)
        return apartments.all()

    async def create_apartment(
        self,
        landlord_id: int,
        name: str,
        city: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> Apartment:
        """Create a new apartment for a landlord.
        
        Args:
            landlord_id: Landlord ID
            name: Apartment name
            city: City name (optional)
            latitude: Latitude coordinate (optional)
            longitude: Longitude coordinate (optional)
            
        Returns:
            The created Apartment object
        """
        apt = Apartment(
            landlord_id=landlord_id,
            name=name,
            city=city,
            latitude=latitude,
            longitude=longitude,
        )
        self.session.add(apt)
        await self.session.flush()
        await self.session.commit()
        
        return apt

    async def update_apartment(
        self,
        landlord_id: int,
        apt_id: int,
        name: str | None = None,
        city: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> Apartment:
        """Update an apartment.
        
        Args:
            landlord_id: Landlord ID (for ownership verification)
            apt_id: Apartment ID
            name: New name (optional)
            city: New city (optional)
            latitude: New latitude (optional)
            longitude: New longitude (optional)
            
        Returns:
            The updated Apartment object
            
        Raises:
            NotFoundError: If apartment not found or doesn't belong to landlord
        """
        apt: Apartment | None = await self.session.get(Apartment, apt_id)
        if not apt or apt.landlord_id != landlord_id:
            raise NotFoundError("Apartment not found")
            
        if name is not None:
            apt.name = name
        if city is not None:
            apt.city = city
        if latitude is not None:
            apt.latitude = latitude
        if longitude is not None:
            apt.longitude = longitude
            
        await self.session.commit()
        return apt

    async def get_dashboard_data(self, user_id: int) -> Dict[str, Any]:
        """Get landlord dashboard data.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with landlord data, apartments, and metrics
            
        Raises:
            NotFoundError: If landlord not found
        """
        # Get landlord data
        stmt = select(Landlord).where(Landlord.user_id == user_id)
        landlord = await self.session.scalar(stmt)
        
        if not landlord:
            raise NotFoundError("Landlord not found")
        
        # Get apartments
        apartments = await self.list_apartments(landlord.id)
        
        # Get metrics (simplified for now)
        # In a real implementation, you would calculate actual metrics from purchases
        metrics = {
            "total_qty": 0,
            "total_amount": "0",
            "last_qty": 0,
            "last_amount": "0"
        }
        
        return {
            "landlord": landlord,
            "apartments": apartments,
            "metrics": metrics
        }

    # Commission Management
    
    async def set_tour_commission(
        self, landlord_id: int, tour_id: int, commission_pct: Decimal
    ) -> Decimal:
        """Set commission percentage for a tour.
        
        Args:
            landlord_id: Landlord ID
            tour_id: Tour ID
            commission_pct: Commission percentage
            
        Returns:
            The set commission percentage
            
        Raises:
            NotFoundError: If tour not found
            ValidationError: If commission exceeds tour's maximum
        """
        tour: Tour | None = await self.session.get(Tour, tour_id)
        if not tour:
            raise NotFoundError("Tour not found")
            
        if commission_pct > tour.max_commission_pct:
            raise ValidationError(
                f"Commission cannot exceed tour's max of {tour.max_commission_pct}"
            )
            
        # Upsert commission row
        stmt = select(LandlordCommission).where(
            LandlordCommission.landlord_id == landlord_id,
            LandlordCommission.tour_id == tour_id,
        )
        lc: LandlordCommission | None = await self.session.scalar(stmt)
        
        if lc is None:
            lc = LandlordCommission(
                landlord_id=landlord_id,
                tour_id=tour_id,
                commission_pct=commission_pct,
            )
            self.session.add(lc)
        else:
            lc.commission_pct = commission_pct
            
        await self.session.commit()
        return lc.commission_pct

    async def list_commissions(
        self, landlord_id: int, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all commission settings for a landlord.
        
        Args:
            landlord_id: Landlord ID
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of commission settings with tour information
        """
        stmt = (
            select(LandlordCommission, Tour.title)
            .join(Tour, LandlordCommission.tour_id == Tour.id)
            .where(LandlordCommission.landlord_id == landlord_id)
            .order_by(Tour.title)
            .limit(limit)
            .offset(offset)
        )
        
        rows = await self.session.execute(stmt)
        
        out = []
        for lc, title in rows:
            out.append({
                "tour_id": lc.tour_id,
                "tour_title": title,
                "commission_pct": lc.commission_pct,
            })
        
        return out

    async def list_tours_with_commission(
        self, landlord_id: int, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all tours with landlord's commission settings.
        
        Args:
            landlord_id: Landlord ID
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of tours with commission information
        """
        stmt = (
            select(
                Tour.id,
                Tour.title,
                Tour.price,
                Tour.max_commission_pct,
                LandlordCommission.commission_pct,
            )
            .outerjoin(
                LandlordCommission,
                (LandlordCommission.tour_id == Tour.id)
                & (LandlordCommission.landlord_id == landlord_id),
            )
            .order_by(Tour.title)
            .limit(limit)
            .offset(offset)
        )
        rows = await self.session.execute(stmt)
        
        out = []
        for tid, title, price, maxc, chosen in rows:
            out.append({
                "id": tid,
                "title": title,
                "price": price,
                "max_commission_pct": maxc,
                "commission_pct": chosen,
            })
        return out

    # Earnings Management
    
    async def get_earnings(
        self, landlord_id: int, period: str = "30d"
    ) -> Dict[str, Any]:
        """Get earnings statistics for a landlord.
        
        Args:
            landlord_id: Landlord ID
            period: Period for calculations ("all" or "Nd" where N is days)
            
        Returns:
            Dictionary with earnings statistics
        """
        # Parse period parameter
        if period == "all":
            cutoff = None
        else:
            try:
                if period.endswith("d"):
                    days = int(period[:-1])
                    cutoff = datetime.utcnow() - timedelta(days=days)
                else:
                    raise ValueError
            except ValueError:
                raise ValidationError("Invalid period value")
        
        # Aggregate totals and earnings using commission stored per purchase
        stmt_base = select(
            func.coalesce(func.sum(Purchase.qty), 0).label("tickets"),
            func.coalesce(
                func.sum(Purchase.amount_gross * (Purchase.commission_pct / Decimal("100"))),
                0
            ).label("earnings"),
        ).where(Purchase.landlord_id == landlord_id)
        
        result_all = await self.session.execute(stmt_base)
        tickets_all, earnings_all = result_all.one()
        
        tickets_all = int(tickets_all or 0)
        earnings_all = Decimal(earnings_all or 0)
        
        if cutoff:
            stmt_30 = stmt_base.where(Purchase.ts >= cutoff)
            result_30 = await self.session.execute(stmt_30)
            tickets_30, earnings_30 = result_30.one()
            tickets_30 = int(tickets_30 or 0)
            earnings_30 = Decimal(earnings_30 or 0)
        else:
            tickets_30 = tickets_all
            earnings_30 = earnings_all
        
        return {
            "total_tickets": tickets_all,
            "tickets_last_30d": tickets_30,
            "total_earnings": earnings_all.quantize(Decimal("0.01")),
            "earnings_last_30d": earnings_30.quantize(Decimal("0.01")),
        }

    async def get_earnings_details(
        self, landlord_id: int, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get detailed earnings records for CSV export.
        
        Args:
            landlord_id: Landlord ID
            days: Number of days to look back
            
        Returns:
            List of purchase records with earnings details
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        stmt = (
            select(Purchase.ts, Purchase.qty, Purchase.amount, Purchase.commission_pct)
            .where(Purchase.landlord_id == landlord_id, Purchase.ts >= cutoff)
            .order_by(Purchase.ts.desc())
        )
        rows = await self.session.execute(stmt)
        
        details = []
        for ts, qty, amount, comm in rows:
            details.append({
                "timestamp": ts.isoformat(),
                "tickets": qty,
                "amount_net": str(amount),
                "commission_pct": str(comm or 0),
            })
        
        return details

    async def get_apartments_for_qr(self, landlord_id: int, apt_id: int | None = None) -> List[Apartment]:
        """Get all apartments for QR code generation.
        
        Args:
            landlord_id: Landlord ID
            apt_id: Optional apartment ID to filter by
        Returns:
            List of Apartment objects
        """
        if apt_id:
            stmt = select(Apartment).where(
                Apartment.landlord_id == landlord_id,
                Apartment.id == apt_id
            )
        else:
            stmt = select(Apartment).where(Apartment.landlord_id == landlord_id)
        stmt = (
            select(Apartment)
            .where(Apartment.landlord_id == landlord_id)
            .order_by(Apartment.id)
        )
        apartments = await self.session.scalars(stmt)
        return apartments.all()

    async def mark_qr_sent(self, landlord_id: int) -> None:
        """Mark that QR codes have been sent to landlord.
        
        Args:
            landlord_id: Landlord ID
        """
        landlord: Landlord | None = await self.session.get(Landlord, landlord_id)
        if landlord and landlord.qr_sent is None:
            landlord.qr_sent = datetime.utcnow()
            await self.session.commit() 