from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import BaseRepository
from app.models import User, Agency


class UserRepository(BaseRepository[User]):
    """User repository implementation"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        query = select(User).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_telegram_id(self, tg_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        query = select(User).where(User.tg_id == tg_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def exists_by_email(self, email: str) -> bool:
        """Check if user exists by email"""
        query = select(User.id).where(User.email == email)
        result = await self.session.execute(query)
        return result.scalar() is not None
    
    async def get_with_agency(self, user_id: int) -> Optional[User]:
        """Get user with agency relationship loaded"""
        query = (
            select(User)
            .options(selectinload(User.agency))
            .where(User.id == user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_role(
        self,
        role: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Get users by role"""
        query = (
            select(User)
            .where(User.role == role)
            .order_by(User.created.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_agency_managers(
        self,
        agency_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """Get managers for a specific agency"""
        query = (
            select(User)
            .where(User.agency_id == agency_id, User.role == "manager")
            .order_by(User.created.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def update_password(self, user_id: int, password_hash: str) -> Optional[User]:
        """Update user password"""
        user = await self.get(user_id)
        if not user:
            return None
        
        user.password_hash = password_hash
        await self.session.flush()
        return user 