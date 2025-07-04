"""Public endpoints."""

from __future__ import annotations

from decimal import Decimal
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ....deps import SessionDep
from ....security import current_user, role_required
from ....services.public_service import PublicService
from ....core.exceptions import NotFoundError, ValidationError
from ..schemas.public_schemas import (
    TourSearchOut,
    TourListOut,
    TourDetailOut,
    CategoryOut,
    QuoteIn,
    QuoteOut,
    DepartureListOut,
    DepartureAvailabilityOut,
    CityOut,
    TourCategoryOut,
    TicketClassOut,
    RepetitionTypeOut,
    LandlordSignupRequest,
)

router = APIRouter()


# Tour Search and Listing
@router.get("/tours/search", response_model=list[TourSearchOut])
async def search_tours(
    sess: SessionDep,
    city: str | None = Query(None, max_length=64),
    price_min: Decimal | None = Query(None, gt=0),
    price_max: Decimal | None = Query(None, gt=0),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    duration_min: int | None = Query(None, gt=0),
    duration_max: int | None = Query(None, gt=0),
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user: dict | None = Depends(lambda: None),
):
    """Search tours with filters and return discounted price."""
    service = PublicService(sess)
    user_id = int(user["sub"]) if user and "sub" in user else None
    
    tours = await service.search_tours(
        user_id=user_id,
        city=city,
        price_min=price_min,
        price_max=price_max,
        date_from=date_from,
        date_to=date_to,
        duration_min=duration_min,
        duration_max=duration_max,
        limit=limit,
        offset=offset,
    )
    
    return [TourSearchOut(**tour) for tour in tours]


@router.get("/tours", response_model=list[TourListOut])
async def list_tours(
    sess: SessionDep,
    limit: int = Query(100, gt=0, le=200),
    offset: int = Query(0, ge=0),
):
    """List tours (lightweight)."""
    service = PublicService(sess)
    tours = await service.list_tours(limit=limit, offset=offset)
    return [TourListOut(**tour) for tour in tours]


@router.get("/tours/{tid}", response_model=TourDetailOut)
async def tour_detail(tid: int, sess: SessionDep):
    """Full tour detail."""
    service = PublicService(sess)
    try:
        tour = await service.get_tour_detail(tid)
        return TourDetailOut(**tour)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# Tour Categories
@router.get("/tours/{tour_id}/categories", response_model=list[CategoryOut])
async def tour_categories(
    tour_id: int, sess: SessionDep, user: dict | None = Depends(lambda: None)
):
    """List ticket categories including discounted price."""
    service = PublicService(sess)
    user_id = int(user["sub"]) if user and "sub" in user else None
    
    try:
        categories = await service.get_tour_categories(tour_id, user_id)
        return [CategoryOut(**cat) for cat in categories]
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# Tour Departures
@router.get("/tours/{tour_id}/departures", response_model=list[DepartureListOut])
async def tour_departures(
    tour_id: int,
    sess: SessionDep,
    limit: int = Query(30, gt=0, le=100),
    offset: int = Query(0, ge=0),
):
    """Upcoming departures for a given tour (with seats left)."""
    service = PublicService(sess)
    try:
        departures = await service.get_tour_departures(tour_id, limit, offset)
        return [DepartureListOut(**dep) for dep in departures]
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/departures/{departure_id}/availability", response_model=DepartureAvailabilityOut)
async def departure_availability(departure_id: int, sess: SessionDep):
    """Seats left for a departure."""
    service = PublicService(sess)
    try:
        availability = await service.get_departure_availability(departure_id)
        return DepartureAvailabilityOut(**availability)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# Price Quote
@router.post(
    "/quote",
    response_model=QuoteOut,
    dependencies=[Depends(role_required("bot_user"))],
)
async def price_quote(payload: QuoteIn, sess: SessionDep, user=Depends(current_user)):
    """Preview price and availability before confirming booking."""
    service = PublicService(sess)
    
    try:
        quote = await service.calculate_price_quote(
            departure_id=payload.departure_id,
            items=[{"category_id": item.category_id, "qty": item.qty} for item in payload.items],
            user_id=int(user["sub"]),
            virtual_timestamp=payload.virtual_timestamp,
        )
        return QuoteOut(**quote)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


# List Endpoints
@router.get("/cities", response_model=list[CityOut])
async def list_cities(sess: SessionDep):
    """Return all cities for dropdown selection."""
    service = PublicService(sess)
    cities = await service.list_cities()
    return [CityOut(**city) for city in cities]


@router.get("/tour_categories", response_model=list[TourCategoryOut])
async def list_tour_categories(sess: SessionDep):
    """Return all tour categories for dropdown selection."""
    service = PublicService(sess)
    categories = await service.list_tour_categories()
    return [TourCategoryOut(**cat) for cat in categories]


@router.get("/ticket_classes", response_model=list[TicketClassOut])
async def list_ticket_classes(sess: SessionDep):
    """Return all ticket classes for dropdown selection."""
    service = PublicService(sess)
    classes = await service.list_ticket_classes()
    return [TicketClassOut(**cls) for cls in classes]


@router.get("/repetition_types", response_model=list[RepetitionTypeOut])
async def list_repetition_types(sess: SessionDep):
    """Return all repetition types for dropdown selection."""
    service = PublicService(sess)
    types = await service.list_repetition_types()
    return [RepetitionTypeOut(**typ) for typ in types]

@router.post("/signup/landlord", status_code=status.HTTP_201_CREATED)
async def landlord_signup(
    payload: LandlordSignupRequest,
    sess: SessionDep
):
    """Create a new landlord user."""
    service = PublicService(sess)
    try:
        result = await service.create_landlord(
            name=payload.name,
            email=payload.email,
            password=payload.password
        )
        return {"success": True, "user_id": result["user_id"]}
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) 