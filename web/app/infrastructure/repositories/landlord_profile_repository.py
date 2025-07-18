from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Landlord


class LandlordProfileRepository:
    """Repository for landlord profile operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, landlord_id: int) -> Landlord:
        """Get landlord by ID"""
        result = await self.session.execute(
            select(Landlord).where(Landlord.id == landlord_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_user_id(self, user_id: int) -> Landlord:
        """Get landlord by user ID"""
        result = await self.session.execute(
            select(Landlord).where(Landlord.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_payment_info(self, landlord_id: int, phone_number: str = None, bank_name: str = None) -> bool:
        """Update landlord's payment information"""
        update_data = {}
        if phone_number is not None:
            update_data["phone_number"] = phone_number
        if bank_name is not None:
            update_data["bank_name"] = bank_name
            
        if not update_data:
            return False
            
        stmt = (
            update(Landlord)
            .where(Landlord.id == landlord_id)
            .values(**update_data)
        )
        
        result = await self.session.execute(stmt)
        return result.rowcount > 0 