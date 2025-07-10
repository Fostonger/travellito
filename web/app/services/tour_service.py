from typing import Optional, List, Dict, Any
from datetime import datetime, time
from decimal import Decimal

from app.core import BaseService, NotFoundError, ValidationError, BusinessLogicError
from app.infrastructure.repositories import TourRepository
from app.models import Tour, TourImage, TicketCategory, TicketClass
from app.storage import upload_image, presigned
from sqlalchemy import select


class TourService(BaseService):
    """Tour service handling business logic"""
    
    def __init__(self, session, tour_repository: Optional[TourRepository] = None):
        super().__init__(session)
        self.tour_repository = tour_repository or TourRepository(session)
    
    async def create_tour(
        self,
        agency_id: int,
        title: str,
        description: Optional[str],
        duration_minutes: Optional[int] = None,
        city_id: Optional[int] = None,
        category_id: Optional[int] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        repeat_type: str = "none",
        repeat_weekdays: Optional[List[int]] = None,
        repeat_time_str: Optional[str] = None,
    ) -> Tour:
        """Create a new tour with validation"""
        
        # Validate repeat configuration
        if repeat_type not in ["none", "daily", "weekly"]:
            raise ValidationError("Invalid repeat type", field="repeat_type")
        
        # Parse repeat time if provided
        repeat_time = None
        if repeat_time_str:
            try:
                hour, minute = map(int, repeat_time_str.split(":"))
                repeat_time = time(hour=hour, minute=minute)
            except (ValueError, AttributeError):
                raise ValidationError("Invalid time format. Use HH:MM", field="repeat_time")
        
        # Validate weekly repeat configuration
        if repeat_type == "weekly":
            if not repeat_weekdays:
                raise ValidationError("Weekly repeat requires weekdays", field="repeat_weekdays")
            if any(day < 0 or day > 6 for day in repeat_weekdays):
                raise ValidationError("Invalid weekday values (0-6)", field="repeat_weekdays")
        
        # Create tour
        tour_data = {
            "agency_id": agency_id,
            "title": title,
            "description": description,
            "duration_minutes": duration_minutes,
            "city_id": city_id,
            "category_id": category_id,
            "latitude": latitude,
            "longitude": longitude,
            "repeat_type": repeat_type,
            "repeat_weekdays": repeat_weekdays,
            "repeat_time": repeat_time,
        }
        
        tour = await self.tour_repository.create(obj_in=tour_data)
        
        return tour
    
    async def _create_default_ticket_category(self, tour_id: int, price: Decimal) -> TicketCategory:
        """Create default ticket category with id 0 for a tour"""
        # Get the ticket class with id 0
        stmt = select(TicketClass).where(TicketClass.id == 0)
        ticket_class = await self.session.scalar(stmt)
        
        if not ticket_class:
            raise ValidationError("Default ticket class with id 0 not found")
        
        # Create ticket category
        category = TicketCategory(
            tour_id=tour_id,
            ticket_class_id=0,
            name=ticket_class.human_name,
            price=price
        )
        
        self.session.add(category)
        await self.session.flush()
        
        return category
    
    async def update_tour(
        self,
        tour_id: int,
        agency_id: int,
        **update_data
    ) -> Tour:
        """Update tour with authorization check"""
        
        # Get tour and verify ownership
        tour = await self.tour_repository.get(tour_id)
        if not tour:
            raise NotFoundError("Tour", tour_id)
        
        if tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)  # Hide existence from unauthorized
        
        # Parse repeat time if provided
        if "repeat_time" in update_data and update_data["repeat_time"]:
            try:
                hour, minute = map(int, update_data["repeat_time"].split(":"))
                update_data["repeat_time"] = time(hour=hour, minute=minute)
            except (ValueError, AttributeError):
                raise ValidationError("Invalid time format. Use HH:MM", field="repeat_time")
        
        # Update tour
        updated_tour = await self.tour_repository.update(id=tour_id, obj_in=update_data)
        if not updated_tour:
            raise NotFoundError("Tour", tour_id)
        
        return updated_tour
    
    async def delete_tour(self, tour_id: int, agency_id: int) -> bool:
        """Delete tour with authorization check"""
        
        # Verify ownership
        tour = await self.tour_repository.get(tour_id)
        if not tour:
            raise NotFoundError("Tour", tour_id)
        
        if tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)
        
        # TODO: Check if tour has departures/bookings before deletion
        
        return await self.tour_repository.delete(id=tour_id)
    
    async def get_agency_tours(
        self,
        agency_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Tour]:
        """Get tours for an agency"""
        return await self.tour_repository.get_by_agency(
            agency_id,
            skip=skip,
            limit=limit
        )
    
    async def add_tour_images(
        self,
        tour_id: int,
        agency_id: int,
        image_files: List[Any]
    ) -> Dict[str, List[str]]:
        """Add images to tour"""
        
        # Verify tour ownership
        tour = await self.tour_repository.get(tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)
        
        if not image_files:
            raise ValidationError("No images provided")
        
        keys = []
        urls = []
        
        for file in image_files:
            # Validate file type
            if not file.content_type.startswith('image/'):
                continue
            
            try:
                # Upload image
                key = upload_image(file)
                if key:
                    # Save to database
                    await self.tour_repository.add_image(tour_id, key)
                    keys.append(key)
                    urls.append(presigned(key))
            except Exception as e:
                # Log error but continue with other images
                print(f"Error uploading image {file.filename}: {str(e)}")
                continue
        
        await self.session.commit()
        
        return {"keys": keys, "urls": urls}
    
    async def add_ticket_category(
        self,
        tour_id: int,
        agency_id: int,
        ticket_class_id: int,
        price: Decimal
    ) -> TicketCategory:
        """Add a ticket category to a tour"""
        
        # Verify tour ownership
        tour = await self.tour_repository.get(tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)
        
        # Validate price
        if price <= 0:
            raise ValidationError("Price must be greater than 0", field="price")
        
        # Check if ticket class exists
        stmt = select(TicketClass).where(TicketClass.id == ticket_class_id)
        ticket_class = await self.session.scalar(stmt)
        
        if not ticket_class:
            raise ValidationError(f"Ticket class with id {ticket_class_id} not found")
        
        # Check if this ticket class is already added to this tour
        stmt = select(TicketCategory).where(
            (TicketCategory.tour_id == tour_id) & 
            (TicketCategory.ticket_class_id == ticket_class_id)
        )
        existing_category = await self.session.scalar(stmt)
        
        if existing_category:
            raise ValidationError(f"Ticket class {ticket_class_id} already exists for this tour")
        
        # Create ticket category
        category = TicketCategory(
            tour_id=tour_id,
            ticket_class_id=ticket_class_id,
            name=ticket_class.human_name,
            price=price
        )
        
        self.session.add(category)
        await self.session.flush()
        
        return category
    
    async def get_tour_ticket_categories(
        self,
        tour_id: int,
        agency_id: int
    ) -> List[TicketCategory]:
        """Get ticket categories for a tour"""
        
        # Verify tour ownership
        tour = await self.tour_repository.get(tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)
        
        # Get ticket categories
        stmt = select(TicketCategory).where(TicketCategory.tour_id == tour_id)
        result = await self.session.execute(stmt)
        
        return list(result.scalars().all())
    
    async def delete_ticket_category(
        self,
        tour_id: int,
        category_id: int,
        agency_id: int
    ) -> None:
        """Delete a ticket category from a tour"""
        
        # Verify tour ownership
        tour = await self.tour_repository.get(tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)
        
        # Get ticket category
        stmt = select(TicketCategory).where(
            (TicketCategory.id == category_id) & 
            (TicketCategory.tour_id == tour_id)
        )
        category = await self.session.scalar(stmt)
        
        if not category:
            raise NotFoundError("TicketCategory", category_id)
        
        # Don't allow deleting the default ticket category (id 0) if it's the only one
        if category.ticket_class_id == 0:
            # Check if there are other categories
            stmt = select(TicketCategory).where(
                (TicketCategory.tour_id == tour_id) & 
                (TicketCategory.ticket_class_id != 0)
            )
            other_categories = await self.session.execute(stmt)
            
            if not list(other_categories.scalars().all()):
                raise BusinessLogicError("Cannot delete the default ticket category. A tour must have at least one ticket category.")
        
        # Delete ticket category
        await self.session.delete(category)
    
    async def update_ticket_category(
        self,
        tour_id: int,
        category_id: int,
        agency_id: int,
        price: Decimal
    ) -> TicketCategory:
        """Update a ticket category price"""
        
        # Verify tour ownership
        tour = await self.tour_repository.get(tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)
        
        # Validate price
        if price <= 0:
            raise ValidationError("Price must be greater than 0", field="price")
        
        # Get ticket category
        stmt = select(TicketCategory).where(
            (TicketCategory.id == category_id) & 
            (TicketCategory.tour_id == tour_id)
        )
        category = await self.session.scalar(stmt)
        
        if not category:
            raise NotFoundError("TicketCategory", category_id)
        
        # Update price
        category.price = price
        await self.session.flush()
        
        return category 