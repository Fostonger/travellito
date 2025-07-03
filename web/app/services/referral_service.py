"""Referral service for QR code scanning and landlord referrals."""

from __future__ import annotations

from datetime import datetime
from typing import Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.base import BaseService
from ..core.exceptions import NotFoundError
from ..models import Referral, Landlord, Apartment


class ReferralService(BaseService):
    """Service for referral operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
    
    async def record_landlord_referral(
        self, user_id: int, landlord_id: int
    ) -> Dict[str, bool]:
        """Record that a user has scanned a landlord's QR code.
        
        If a referral row for the same (user, landlord) already exists, 
        just update its timestamp. Otherwise insert a new row.
        
        Args:
            user_id: User ID
            landlord_id: Landlord ID
            
        Returns:
            Dict with ok=True
            
        Raises:
            NotFoundError: If landlord not found
        """
        # Validate landlord exists
        landlord: Landlord | None = await self.session.get(Landlord, landlord_id)
        if not landlord:
            raise NotFoundError("Landlord not found")
        
        # Check if referral already exists
        stmt = select(Referral).where(
            Referral.user_id == user_id,
            Referral.landlord_id == landlord_id,
        )
        ref: Referral | None = await self.session.scalar(stmt)
        
        if ref is None:
            # Create new referral
            ref = Referral(
                user_id=user_id,
                landlord_id=landlord_id,
                ts=datetime.utcnow()
            )
            self.session.add(ref)
        else:
            # Update timestamp
            ref.ts = datetime.utcnow()
        
        await self.session.commit()
        return {"ok": True}
    
    async def record_apartment_scan(
        self, user_id: int, apartment_id: int
    ) -> Dict[str, bool]:
        """Record QR scan by apartment ID.
        
        Resolves landlord via the apartment and records the referral.
        
        Args:
            user_id: User ID
            apartment_id: Apartment ID
            
        Returns:
            Dict with ok=True
            
        Raises:
            NotFoundError: If apartment not found
        """
        apt: Apartment | None = await self.session.get(Apartment, apartment_id)
        if not apt:
            raise NotFoundError("Apartment not found")
        
        # Delegate to landlord referral logic
        return await self.record_landlord_referral(user_id, apt.landlord_id) 