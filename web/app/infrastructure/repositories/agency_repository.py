from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import BaseRepository
from app.models import Agency, Tour


class AgencyRepository(BaseRepository[Agency]):
    """Agency repository implementation"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Agency, session)
    
    async def get_by_name(self, name: str) -> Optional[Agency]:
        """Get agency by name"""
        query = select(Agency).where(Agency.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_with_tours(self, agency_id: int) -> Optional[Agency]:
        """Get agency with tours loaded"""
        query = (
            select(Agency)
            .options(selectinload(Agency.tours))
            .where(Agency.id == agency_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def exists_by_name(self, name: str) -> bool:
        """Check if agency exists by name"""
        query = select(Agency.id).where(Agency.name == name)
        result = await self.session.execute(query)
        return result.scalar() is not None 