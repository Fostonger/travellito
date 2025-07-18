from typing import Optional

from app.core.unit_of_work import UnitOfWork
from app.models import Landlord


class LandlordProfileService:
    """Service for landlord profile operations"""
    
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        
    async def get_landlord_profile(self, user_id: int) -> Optional[Landlord]:
        """Get landlord profile by user ID"""
        async with self.uow:
            return await self.uow.landlord_profile.get_by_user_id(user_id)

    async def get_landlord_profile_by_id(self, landlord_id: int) -> Optional[Landlord]:
        """Get landlord profile by landlord ID"""
        async with self.uow:
            return await self.uow.landlord_profile.get_by_id(landlord_id)
            
    async def update_payment_info(self, landlord_id: int, phone_number: Optional[str] = None, bank_name: Optional[str] = None) -> bool:
        """Update landlord's payment information"""
        async with self.uow:
            result = await self.uow.landlord_profile.update_payment_info(
                landlord_id=landlord_id,
                phone_number=phone_number,
                bank_name=bank_name
            )
            if result:
                await self.uow.commit()
            return result 