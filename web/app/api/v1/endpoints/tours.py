from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, status, Query

from app.api.v1.schemas import TourIn, TourOut, TourUpdate, ImagesOut, TicketCategoryIn, TicketCategoryOut
from app.api.v1.endpoints.utils import get_agency_id
from app.deps import SessionDep
from app.security import current_user, role_required
from app.services import TourService
from app.core import BaseError


router = APIRouter()

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
    
    tour = await service.create_tour(
        agency_id=agency_id,
        title=payload.title,
        description=payload.description,
        duration_minutes=payload.duration_minutes,
        city_id=payload.city_id,
        category_id=payload.category_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        repeat_type=payload.repeat_type or "none",
        repeat_weekdays=payload.repeat_weekdays,
        repeat_time_str=payload.repeat_time,
    )
    
    await sess.commit()
    await sess.refresh(tour)
    
    return TourOut.model_validate(tour)


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
    
    tour = await service.update_tour(
        tour_id=tour_id,
        agency_id=agency_id,
        **update_data
    )
    
    await sess.commit()
    await sess.refresh(tour)
    
    return TourOut.model_validate(tour)


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