from __future__ import annotations
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.landlord_profile_repository import LandlordProfileRepository


class UnitOfWork:
    """Unit of work for managing repository instances and transactions."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.landlord_profile = LandlordProfileRepository(session)
    
    async def __aenter__(self) -> UnitOfWork:
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
    
    async def commit(self):
        await self.session.commit()
    
    async def rollback(self):
        await self.session.rollback()


@asynccontextmanager
async def get_uow(session: AsyncSession) -> AsyncGenerator[UnitOfWork, None]:
    """Get unit of work instance."""
    uow = UnitOfWork(session)
    try:
        yield uow
    except Exception:
        await uow.rollback()
        raise 