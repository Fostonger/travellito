from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, status, Query
import pytz
from datetime import datetime, time

from app.api.v1.schemas import TourIn, TourOut, TourUpdate, ImagesOut, TicketCategoryIn, TicketCategoryOut
from app.api.v1.endpoints.utils import get_agency_id
from app.deps import SessionDep
from app.security import current_user, role_required
from app.services import TourService
from app.core import BaseError


router = APIRouter()

def convert_to_local_time(tour, timezone_str="UTC"):
    """Convert UTC time to local time for frontend display"""
    if not tour.repeat_time:
        return tour

    try:
        # Validate and parse the timezone
        try:
            tz = pytz.timezone(timezone_str)
            print(f"Converting time using timezone: {timezone_str}")
        except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
            print(f"Invalid timezone '{timezone_str}', falling back to UTC")
            tz = pytz.UTC
        
        # Use today's date with the tour's time to create a datetime object
        today = datetime.now().date()
        utc_dt = datetime.combine(today, tour.repeat_time).replace(tzinfo=pytz.UTC)
        
        # Convert to the requested timezone
        local_dt = utc_dt.astimezone(tz)
        
        # Format the time as HH:MM
        local_time = local_dt.strftime("%H:%M")
        
        # Add the local time to the tour object
        setattr(tour, 'local_time', local_time)
    except Exception as e:
        print(f"Error converting time: {str(e)}")
        # Set local_time to repeat_time as fallback
        if hasattr(tour, 'repeat_time') and tour.repeat_time:
            setattr(tour, 'local_time', tour.repeat_time.strftime("%H:%M"))
    
    return tour

@router.get("/list", response_model=List[TourOut])
async def list_tours(
    sess: SessionDep,
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    """List tours for the authenticated agency"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    tours = await service.get_agency_tours(
        agency_id=agency_id,
        skip=offset,
        limit=limit
    )

    print(tours)
    
    # Convert UTC times to local times
    for tour in tours:
        convert_to_local_time(tour)
    
    return [TourOut.model_validate(tour) for tour in tours]


@router.post("/create", response_model=TourOut, status_code=status.HTTP_201_CREATED)
async def create_tour(
    payload: TourIn,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Create a new tour"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    # Ensure timezone is never None
    timezone = payload.timezone if payload.timezone is not None else "UTC"
    
    tour = await service.create_tour(
        agency_id=agency_id,
        title=payload.title,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        city_id=payload.city_id,
        category_id=payload.category_id,
        category_ids=payload.category_ids,
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        repeat_type=payload.repeat_type or "none",
        repeat_weekdays=payload.repeat_weekdays,
        repeat_time_str=payload.repeat_time,
        timezone=timezone,  # Pass the timezone parameter
    )
    
    await sess.commit()
    
    # Get the tour with relationships eagerly loaded to avoid lazy loading issues
    tour_with_categories = await service.get_tour(tour.id, agency_id)
    
    return TourOut.model_validate(tour_with_categories)


@router.patch("/{tour_id}", response_model=TourOut)
async def update_tour(
    tour_id: int,
    payload: TourUpdate,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Update an existing tour"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    update_data = payload.model_dump(exclude_unset=True)
    
    # Ensure timezone is properly passed to the service
    # if repeat_time is being updated
    if "repeat_time" in update_data:
        # Add default timezone if not provided but time is being updated
        if "timezone" not in update_data or not update_data["timezone"]:
            print("No timezone provided, using UTC as fallback")
            update_data["timezone"] = "UTC"
        else:
            print(f"Using timezone from request: {update_data['timezone']}")
    
    # Ensure category_ids is properly passed to the service
    tour = await service.update_tour(
        tour_id=tour_id,
        agency_id=agency_id,
        **update_data
    )
    
    await sess.commit()
    
    # Get the tour with relationships eagerly loaded to avoid lazy loading issues
    tour_with_categories = await service.get_tour(tour_id, agency_id)
    
    # Convert UTC time to local time using the timezone from the request
    timezone_str = update_data.get("timezone", "UTC") if "repeat_time" in update_data else "UTC"
    convert_to_local_time(tour_with_categories, timezone_str)
    
    return TourOut.model_validate(tour_with_categories)


@router.delete("/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tour(
    tour_id: int,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Delete a tour"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    await service.delete_tour(tour_id=tour_id, agency_id=agency_id)
    await sess.commit()
    
    return None


@router.post("/{tour_id}/images", response_model=ImagesOut, status_code=status.HTTP_201_CREATED)
async def upload_tour_images(
    tour_id: int,
    sess: SessionDep,
    files: List[UploadFile] = File(...),
    user=Depends(current_user),
):
    """Upload images for a tour"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    result = await service.add_tour_images(
        tour_id=tour_id,
        agency_id=agency_id,
        image_files=files
    )
    
    return ImagesOut(**result) 


@router.post("/{tour_id}/categories", response_model=TicketCategoryOut, status_code=status.HTTP_201_CREATED)
async def add_ticket_category(
    tour_id: int,
    payload: TicketCategoryIn,
    sess: SessionDep,
    user=Depends(current_user),
):
    """Add a ticket category to a tour"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    category = await service.add_ticket_category(
        tour_id=tour_id,
        agency_id=agency_id,
        ticket_class_id=payload.ticket_class_id,
        price=payload.price
    )
    
    await sess.commit()
    await sess.refresh(category)
    
    return TicketCategoryOut.model_validate(category)


@router.patch("/{tour_id}/categories/{category_id}", response_model=TicketCategoryOut)
async def update_ticket_category(
    tour_id: int,
    category_id: int,
    payload: TicketCategoryIn,
    sess: SessionDep,
    user=Depends(current_user),
):
    """Update a ticket category price"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    category = await service.update_ticket_category(
        tour_id=tour_id,
        category_id=category_id,
        agency_id=agency_id,
        price=payload.price
    )
    
    await sess.commit()
    await sess.refresh(category)
    
    return TicketCategoryOut.model_validate(category)


@router.get("/{tour_id}/categories", response_model=List[TicketCategoryOut])
async def list_ticket_categories(
    tour_id: int,
    sess: SessionDep,
    user=Depends(current_user),
):
    """List ticket categories for a tour"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    categories = await service.get_tour_ticket_categories(
        tour_id=tour_id,
        agency_id=agency_id
    )
    
    return [TicketCategoryOut.model_validate(cat) for cat in categories]


@router.delete("/{tour_id}/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket_category(
    tour_id: int,
    category_id: int,
    sess: SessionDep,
    user=Depends(current_user),
):
    """Delete a ticket category from a tour"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    await service.delete_ticket_category(
        tour_id=tour_id,
        category_id=category_id,
        agency_id=agency_id
    )
    
    await sess.commit()
    
    return None 


@router.get("/{tour_id}", response_model=TourOut)
async def get_tour(
    tour_id: int,
    sess: SessionDep,
    user=Depends(current_user),
):
    """Get a specific tour by ID"""
    agency_id = get_agency_id(user)
    service = TourService(sess)
    
    # Get tour and verify ownership
    tour = await service.get_tour(tour_id, agency_id)
    
    # Convert UTC time to local time
    convert_to_local_time(tour)
    
    return TourOut.model_validate(tour) 