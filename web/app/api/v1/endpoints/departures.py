from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query

from app.api.v1.schemas.departure_schemas import (
    DepartureIn, DepartureOut, DepartureUpdate, CapacityUpdate
)
from app.deps import SessionDep
from app.security import current_user
from app.services import DepartureService
from app.core import BaseError


router = APIRouter()


def get_agency_id(user: dict) -> int:
    """Extract agency ID from user token"""
    agency_id = user.get("agency_id")
    if not agency_id:
        raise BaseError("No agency associated with user", status_code=403)
    return int(agency_id)


@router.get("/", response_model=List[DepartureOut])
async def list_departures(
    sess: SessionDep,
    tour_id: Optional[int] = Query(None, gt=0),
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    """List departures for the authenticated agency"""
    agency_id = get_agency_id(user)
    service = DepartureService(sess)
    
    departures = await service.get_agency_departures(
        agency_id=agency_id,
        tour_id=tour_id,
        skip=offset,
        limit=limit
    )
    
    return [DepartureOut.model_validate(d) for d in departures]


@router.post("/", response_model=DepartureOut, status_code=status.HTTP_201_CREATED)
async def create_departure(
    payload: DepartureIn,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Create a new departure"""
    agency_id = get_agency_id(user)
    service = DepartureService(sess)
    
    departure = await service.create_departure(
        agency_id=agency_id,
        tour_id=payload.tour_id,
        starts_at=payload.starts_at,
        capacity=payload.capacity
    )
    
    await sess.commit()
    await sess.refresh(departure)
    
    return DepartureOut.model_validate(departure)


@router.patch("/{departure_id}", response_model=DepartureOut)
async def update_departure(
    departure_id: int,
    payload: DepartureUpdate,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Update an existing departure"""
    agency_id = get_agency_id(user)
    service = DepartureService(sess)
    
    departure = await service.update_departure(
        departure_id=departure_id,
        agency_id=agency_id,
        starts_at=payload.starts_at,
        capacity=payload.capacity
    )
    
    await sess.commit()
    await sess.refresh(departure)
    
    return DepartureOut.model_validate(departure)


@router.patch("/{departure_id}/capacity", response_model=DepartureOut)
async def update_capacity(
    departure_id: int,
    payload: CapacityUpdate,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Update departure capacity only"""
    agency_id = get_agency_id(user)
    service = DepartureService(sess)
    
    departure = await service.update_departure(
        departure_id=departure_id,
        agency_id=agency_id,
        capacity=payload.capacity
    )
    
    await sess.commit()
    await sess.refresh(departure)
    
    return DepartureOut.model_validate(departure)


@router.delete("/{departure_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_departure(
    departure_id: int,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Delete a departure"""
    agency_id = get_agency_id(user)
    service = DepartureService(sess)
    
    await service.delete_departure(
        departure_id=departure_id,
        agency_id=agency_id
    )
    
    await sess.commit()
    
    return None 