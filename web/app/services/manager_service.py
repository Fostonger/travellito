"""Manager service for agency manager operations."""

from __future__ import annotations

from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.base import BaseService
from ..core.exceptions import NotFoundError, ConflictError
from ..models import User
from ..api.auth import hash_password


class ManagerService(BaseService):
    """Service for agency manager operations."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session)
    
    async def list_managers(self, agency_id: int) -> List[User]:
        """List all managers for an agency.
        
        Args:
            agency_id: Agency ID
            
        Returns:
            List of User objects with manager role
        """
        stmt = select(User).where(
            User.agency_id == agency_id,
            User.role == "manager"
        )
        result = await self.session.scalars(stmt)
        return result.all()
    
    async def create_manager(
        self,
        agency_id: int,
        email: str,
        password: str,
        first: str | None = None,
        last: str | None = None,
    ) -> User:
        """Create a new manager for an agency.
        
        Args:
            agency_id: Agency ID
            email: Manager email
            password: Manager password (will be hashed)
            first: First name (optional)
            last: Last name (optional)
            
        Returns:
            The created User object
            
        Raises:
            ConflictError: If email already exists
        """
        # Check if email already exists
        existing = await self.session.scalar(
            select(User).where(User.email == email)
        )
        if existing:
            raise ConflictError("Email already exists")
        
        # Create new manager
        manager = User(
            email=email,
            password_hash=hash_password(password),
            role="manager",
            agency_id=agency_id,
            first=first,
            last=last,
        )
        
        self.session.add(manager)
        await self.session.commit()
        await self.session.refresh(manager)
        
        return manager
    
    async def delete_manager(self, agency_id: int, manager_id: int) -> None:
        """Delete a manager from an agency.
        
        Args:
            agency_id: Agency ID (for ownership verification)
            manager_id: Manager ID to delete
            
        Raises:
            NotFoundError: If manager not found or doesn't belong to agency
        """
        manager: User | None = await self.session.get(User, manager_id)
        
        if not manager or manager.agency_id != agency_id or manager.role != "manager":
            raise NotFoundError("Manager not found")
        
        await self.session.delete(manager)
        await self.session.commit() 