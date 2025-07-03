"""Helper functions shared across endpoints."""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ....models import PurchaseItem, Purchase


async def seats_taken(session: AsyncSession, departure_id: int) -> int:
    """Calculate total seats taken for a departure.
    
    Args:
        session: Database session
        departure_id: Departure ID
        
    Returns:
        Total number of seats taken
    """
    stmt = (
        select(func.coalesce(func.sum(PurchaseItem.qty), 0))
        .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
        .where(Purchase.departure_id == departure_id)
    )
    taken: int = await session.scalar(stmt)
    return taken or 0 