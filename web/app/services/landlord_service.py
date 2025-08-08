"""Landlord service for landlord operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy import select, func, literal, column, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ValidationError
from ..models import (
    Apartment, Landlord, Purchase, Tour, Departure, LandlordCommission,
    TicketCategory, Referral, Setting
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
            List of Apartment objects with eagerly loaded city relationship
        """
        from sqlalchemy.orm import selectinload
        
        stmt = (
            select(Apartment)
            .options(selectinload(Apartment.city))
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
        city_id: int,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> Apartment:
        """Create a new apartment for a landlord.
        
        Args:
            landlord_id: Landlord ID
            name: Apartment name
            city_id: City ID
            latitude: Latitude coordinate (optional)
            longitude: Longitude coordinate (optional)
            
        Returns:
            The created Apartment object
        """
        apt = Apartment(
            landlord_id=landlord_id,
            name=name,
            city_id=city_id,
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
        city_id: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> Apartment:
        """Update an apartment.
        
        Args:
            landlord_id: Landlord ID (for ownership verification)
            apt_id: Apartment ID
            name: New name (optional)
            city_id: New city ID (optional)
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
        if city_id is not None:
            apt.city_id = city_id
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
        from datetime import datetime, timedelta
        
        # Get landlord data
        stmt = select(Landlord).where(Landlord.user_id == user_id)
        landlord = await self.session.scalar(stmt)
        
        if not landlord:
            raise NotFoundError("Landlord not found")
        
        # Get apartments
        apartments = await self.list_apartments(landlord.id)
        
        # Get apartment IDs for this landlord
        apartment_ids = [apt.id for apt in apartments]
        
        if not apartment_ids:
            # No apartments, return zero metrics
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
        
        # Calculate metrics from purchases with apartment_id referrals
        # Get all confirmed purchases with apartment_id in the landlord's apartments
        stmt_all = (
            select(
                func.count(Purchase.id).label("count"),
                func.sum(Purchase.qty).label("qty"),
                func.ceil(func.sum(Purchase.amount * Tour.max_commission_pct / 100)).label("amount")
            )
            .join(Departure, Purchase.departure_id == Departure.id)
            .join(Tour, Departure.tour_id == Tour.id)
            .where(
                Purchase.apartment_id.in_(apartment_ids),
                Purchase.status == "confirmed"
            )
        )
        
        # Get purchases from the last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        stmt_recent = (
            select(
                func.count(Purchase.id).label("count"),
                func.sum(Purchase.qty).label("qty"),
                func.ceil(func.sum(Purchase.amount * Tour.max_commission_pct / 100)).label("amount")
            )
            .join(Departure, Purchase.departure_id == Departure.id)
            .join(Tour, Departure.tour_id == Tour.id)
            .where(
                Purchase.apartment_id.in_(apartment_ids),
                Purchase.status == "confirmed",
                Purchase.ts >= thirty_days_ago
            )
        )
        
        # Execute both queries
        result_all = await self.session.execute(stmt_all)
        all_count, all_qty, all_amount = result_all.one()
        
        result_recent = await self.session.execute(stmt_recent)
        recent_count, recent_qty, recent_amount = result_recent.one()
        
        # Handle None values
        all_qty = int(all_qty or 0)
        all_amount = all_amount or Decimal("0")
        recent_qty = int(recent_qty or 0)
        recent_amount = recent_amount or Decimal("0")
        
        metrics = {
            "total_qty": all_qty,
            "total_amount": str(all_amount),
            "last_qty": recent_qty,
            "last_amount": str(recent_amount)
        }
        
        return {
            "landlord": landlord,
            "apartments": apartments,
            "metrics": metrics
        }

    async def get_qr_template_settings(self) -> dict | None:
        """Get QR template settings from admin settings.
        
        Returns:
            Dictionary with template settings or None
        """
        from sqlalchemy import select
        from ..models import Setting
        
        # Get QR template settings
        settings = {}
        
        # Get template URL
        template_url = await self.session.scalar(
            select(Setting).where(Setting.key == "qr_template_url")
        )
        if template_url:
            settings["template_url"] = template_url.value
            
            # Get position and size settings
            pos_x = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_pos_x")
            )
            pos_y = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_pos_y")
            )
            width = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_width")
            )
            height = await self.session.scalar(
                select(Setting).where(Setting.key == "qr_template_height")
            )
            
            settings["position_x"] = int(pos_x.value) if pos_x else 50
            settings["position_y"] = int(pos_y.value) if pos_y else 50
            settings["width"] = int(width.value) if width else 200
            settings["height"] = int(height.value) if height else 200
            
        return settings if settings else None

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
            Dictionary with earnings statistics including both direct referrals and apartment referrals
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
        
        # Get apartment IDs for this landlord
        stmt_apartments = select(Apartment.id).where(Apartment.landlord_id == landlord_id)
        apartment_ids = [row[0] for row in await self.session.execute(stmt_apartments)]
        
        # Aggregate totals and earnings from direct referrals
        stmt_base_direct = select(
            func.coalesce(func.sum(Purchase.qty), 0).label("tickets"),
            func.coalesce(
                func.sum(Purchase.amount * (Purchase.commission_pct / Decimal("100"))),
                0
            ).label("earnings"),
        ).where(Purchase.landlord_id == landlord_id, Purchase.status == "confirmed")
        
        # Aggregate totals and earnings from apartment referrals
        stmt_base_apt = select(
            func.coalesce(func.sum(Purchase.qty), 0).label("tickets"),
            func.coalesce(func.sum(Purchase.amount), 0).label("earnings"),
        ).where(
            Purchase.apartment_id.in_(apartment_ids) if apartment_ids else False,
            Purchase.status == "confirmed"
        )
        
        # Get all-time metrics
        result_direct_all = await self.session.execute(stmt_base_direct)
        tickets_direct_all, earnings_direct_all = result_direct_all.one()
        
        result_apt_all = await self.session.execute(stmt_base_apt)
        tickets_apt_all, earnings_apt_all = result_apt_all.one()
        
        # Convert to appropriate types
        tickets_direct_all = int(tickets_direct_all or 0)
        earnings_direct_all = Decimal(earnings_direct_all or 0)
        tickets_apt_all = int(tickets_apt_all or 0)
        earnings_apt_all = Decimal(earnings_apt_all or 0)
        
        # Calculate totals
        tickets_all = tickets_direct_all + tickets_apt_all
        earnings_all = earnings_direct_all + earnings_apt_all
        
        # Default values for period metrics
        tickets_period = tickets_all
        earnings_period = earnings_all
        
        if cutoff:
            # Get period-specific metrics for direct referrals
            stmt_direct_period = stmt_base_direct.where(Purchase.ts >= cutoff)
            result_direct_period = await self.session.execute(stmt_direct_period)
            tickets_direct_period, earnings_direct_period = result_direct_period.one()
            
            # Get period-specific metrics for apartment referrals
            stmt_apt_period = stmt_base_apt.where(Purchase.ts >= cutoff)
            result_apt_period = await self.session.execute(stmt_apt_period)
            tickets_apt_period, earnings_apt_period = result_apt_period.one()
            
            # Convert to appropriate types
            tickets_direct_period = int(tickets_direct_period or 0)
            earnings_direct_period = Decimal(earnings_direct_period or 0)
            tickets_apt_period = int(tickets_apt_period or 0)
            earnings_apt_period = Decimal(earnings_apt_period or 0)
            
            # Calculate period totals
            tickets_period = tickets_direct_period + tickets_apt_period
            earnings_period = earnings_direct_period + earnings_apt_period
        
        return {
            "total_tickets": tickets_all,
            "tickets_last_30d": tickets_period,
            "total_earnings": earnings_all.quantize(Decimal("0.01")),
            "earnings_last_30d": earnings_period.quantize(Decimal("0.01")),
            "direct_referral_tickets": tickets_direct_all,
            "direct_referral_earnings": earnings_direct_all.quantize(Decimal("0.01")),
            "apartment_referral_tickets": tickets_apt_all,
            "apartment_referral_earnings": earnings_apt_all.quantize(Decimal("0.01")),
        }

    async def get_earnings_details(
        self, landlord_id: int, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get detailed earnings records for CSV export.
        
        Args:
            landlord_id: Landlord ID
            days: Number of days to look back
            
        Returns:
            List of purchase records with earnings details including both direct and apartment referrals
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get apartment IDs for this landlord
        stmt_apartments = select(Apartment.id).where(Apartment.landlord_id == landlord_id)
        apartment_ids = [row[0] for row in await self.session.execute(stmt_apartments)]
        
        # Get direct referral purchases
        stmt_direct = (
            select(
                Purchase.id,
                Purchase.ts,
                Purchase.qty,
                Purchase.amount,
                Purchase.commission_pct,
                literal('direct').label('referral_type')
            )
            .where(
                Purchase.landlord_id == landlord_id,
                Purchase.status == "confirmed",
                Purchase.ts >= cutoff
            )
        )
        
        # Get apartment referral purchases
        stmt_apt = (
            select(
                Purchase.id,
                Purchase.ts,
                Purchase.qty,
                Purchase.amount,
                literal('apartment').label('referral_type'),
                Apartment.name.label('apartment_name')
            )
            .join(Apartment, Purchase.apartment_id == Apartment.id)
            .where(
                Purchase.apartment_id.in_(apartment_ids) if apartment_ids else False,
                Purchase.status == "confirmed",
                Purchase.ts >= cutoff
            )
        )
        
        # Union the two queries and order by timestamp
        stmt = stmt_direct.union(stmt_apt).order_by(desc(column('ts')))

        comm_pct = select(Setting).where(Setting.key == "default_max_commission")
        comm_pct_res = await self.session.scalar(comm_pct)

        rows = await self.session.execute(stmt)
        
        details = []
        for row in rows:
            purchase_id, ts, qty, amount, referral_type = row[:6]
            apartment_name = row[6] if len(row) > 6 and referral_type == 'apartment' else None
            
            detail = {
                "id": purchase_id,
                "timestamp": ts.isoformat(),
                "tickets": qty,
                "amount_net": str(amount),
                "referral_type": referral_type
            }
            
            if referral_type == 'direct':
                detail["commission_pct"] = str(comm_pct_res or 0)
            elif referral_type == 'apartment':
                detail["apartment_name"] = apartment_name
                
            details.append(detail)
        
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
            stmt = select(Apartment).where(Apartment.landlord_id == landlord_id).order_by(Apartment.id)
        
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
