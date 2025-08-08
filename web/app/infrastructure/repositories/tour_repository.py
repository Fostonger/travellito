from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import BaseRepository
from app.models import Tour, TourImage, Departure


class ITourRepository(BaseRepository[Tour]):
    """Tour repository interface"""
    
    async def get_by_agency(
        self,
        agency_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Tour]:
        """Get tours by agency"""
        pass
    
    async def get_with_images(self, tour_id: int) -> Optional[Tour]:
        """Get tour with images loaded"""
        pass
    
    async def add_image(self, tour_id: int, image_key: str) -> TourImage:
        """Add image to tour"""
        pass


class TourRepository(ITourRepository):
    """Tour repository implementation"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Tour, session)
    
    async def get(self, id: Any) -> Optional[Tour]:
        """Override get method to eagerly load tour_categories"""
        query = (
            select(Tour)
            .options(
                selectinload(Tour.tour_categories),
                selectinload(Tour.repetitions),
            )
            .where(Tour.id == id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_agency(
        self,
        agency_id: int,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Tour]:
        """Get tours by agency with pagination"""
        query = (
            select(Tour)
            .where(Tour.agency_id == agency_id)
            .options(
                selectinload(Tour.tour_categories),
                selectinload(Tour.repetitions),
            )
            .order_by(Tour.id.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_with_images(self, tour_id: int) -> Optional[Tour]:
        """Get tour with images eagerly loaded"""
        query = (
            select(Tour)
            .options(
                selectinload(Tour.images),
                selectinload(Tour.tour_categories),
                selectinload(Tour.repetitions),
            )
            .where(Tour.id == tour_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def add_image(self, tour_id: int, image_key: str) -> TourImage:
        """Add image to tour"""
        image = TourImage(tour_id=tour_id, key=image_key)
        self.session.add(image)
        await self.session.flush()
        return image
    
    async def search(
        self,
        *,
        city_id: Optional[int] = None,
        category_id: Optional[int] = None,  # Kept for API compatibility
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Tour]:
        """Search tours with filters"""
        query = select(Tour).options(
            selectinload(Tour.tour_categories)
        )
        
        conditions = []
        if city_id:
            conditions.append(Tour.city_id == city_id)
        # If category_id is provided, we need to join with tour_category_associations
        # and filter by category_id there
        if category_id:
            from app.models import TourCategoryAssociation
            query = (
                query.join(TourCategoryAssociation, 
                           Tour.id == TourCategoryAssociation.tour_id)
                .where(TourCategoryAssociation.category_id == category_id)
            )
        if min_price is not None:
            conditions.append(Tour.price >= min_price)
        if max_price is not None:
            conditions.append(Tour.price <= max_price)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Tour.id.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()) 