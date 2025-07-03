from typing import Optional, List
from datetime import datetime, timedelta

from app.core import BaseService, NotFoundError, ValidationError, ConflictError, BusinessLogicError
from app.infrastructure.repositories import DepartureRepository, TourRepository
from app.models import Departure, Tour


class DepartureService(BaseService):
    """Departure service handling business logic"""
    
    def __init__(self, session, departure_repo: Optional[DepartureRepository] = None, 
                 tour_repo: Optional[TourRepository] = None):
        super().__init__(session)
        self.departure_repo = departure_repo or DepartureRepository(session)
        self.tour_repo = tour_repo or TourRepository(session)
    
    async def create_departure(
        self,
        agency_id: int,
        tour_id: int,
        starts_at: datetime,
        capacity: int
    ) -> Departure:
        """Create departure with validation"""
        
        # Validate capacity
        if capacity <= 0:
            raise ValidationError("Capacity must be greater than 0", field="capacity")
        
        # Validate tour exists and belongs to agency
        tour = await self.tour_repo.get(tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Tour", tour_id)
        
        # Create departure
        departure_data = {
            "tour_id": tour_id,
            "starts_at": starts_at,
            "capacity": capacity,
            "modifiable": True
        }
        
        return await self.departure_repo.create(obj_in=departure_data)
    
    async def update_departure(
        self,
        departure_id: int,
        agency_id: int,
        starts_at: Optional[datetime] = None,
        capacity: Optional[int] = None
    ) -> Departure:
        """Update departure with validation and locking"""
        
        # Get departure with lock
        departure = await self.departure_repo.lock_for_update(departure_id)
        if not departure:
            raise NotFoundError("Departure", departure_id)
        
        # Verify tour ownership
        tour = await self.tour_repo.get(departure.tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Departure", departure_id)
        
        # Check if departure is modifiable
        if not departure.modifiable:
            raise BusinessLogicError(
                "Departure cannot be modified after free cancellation cutoff",
                rule="free_cancellation_policy"
            )
        
        update_data = {}
        
        # Validate and update capacity
        if capacity is not None:
            if capacity <= 0:
                raise ValidationError("Capacity must be greater than 0", field="capacity")
            
            # Check if new capacity is lower than booked seats
            seats_taken = await self.departure_repo.get_seats_taken(departure_id)
            if capacity < seats_taken:
                raise ConflictError(
                    f"Cannot set capacity to {capacity}, {seats_taken} seats already booked"
                )
            
            update_data["capacity"] = capacity
        
        # Update starts_at
        if starts_at is not None:
            update_data["starts_at"] = starts_at
        
        if update_data:
            departure = await self.departure_repo.update(
                id=departure_id,
                obj_in=update_data
            )
        
        return departure
    
    async def delete_departure(
        self,
        departure_id: int,
        agency_id: int
    ) -> bool:
        """Delete departure with validation"""
        
        # Get departure
        departure = await self.departure_repo.get(departure_id)
        if not departure:
            raise NotFoundError("Departure", departure_id)
        
        # Verify tour ownership
        tour = await self.tour_repo.get(departure.tour_id)
        if not tour or tour.agency_id != agency_id:
            raise NotFoundError("Departure", departure_id)
        
        # Check if departure has bookings
        seats_taken = await self.departure_repo.get_seats_taken(departure_id)
        if seats_taken > 0:
            raise ConflictError("Cannot delete departure with existing bookings")
        
        return await self.departure_repo.delete(id=departure_id)
    
    async def get_agency_departures(
        self,
        agency_id: int,
        tour_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Departure]:
        """Get departures for agency"""
        return await self.departure_repo.get_by_agency(
            agency_id,
            tour_id=tour_id,
            skip=skip,
            limit=limit
        )
    
    async def check_and_lock_departures(self) -> int:
        """Check and lock departures past their free cancellation cutoff"""
        
        now = datetime.utcnow()
        departures = await self.departure_repo.get_modifiable_before_cutoff()
        
        locked_count = 0
        for departure in departures:
            tour = departure.tour
            cutoff = departure.starts_at - timedelta(hours=tour.free_cancellation_cutoff_h)
            
            if now >= cutoff:
                await self.departure_repo.update(
                    id=departure.id,
                    obj_in={"modifiable": False}
                )
                locked_count += 1
        
        if locked_count > 0:
            await self.session.commit()
        
        return locked_count 