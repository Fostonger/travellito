from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import date
from typing import Sequence, Optional, List
from ..models import Tour, Departure, Purchase, TicketCategory, Referral, LandlordCommission, City, TourCategory, TicketClass
from ..security import role_required, current_user
from ..deps import SessionDep
from ..storage import presigned
from pydantic import BaseModel, Field

router = APIRouter()

HUNDRED = Decimal("100")  # module-level constant avoids re-construction

# ---------------------------------------------------------------------------
#  Helpers (shared with multiple handlers)
# ---------------------------------------------------------------------------

async def _last_referral_landlord_id(sess: SessionDep, user_id: int) -> int | None:
    """Return landlord_id of the *most recent* referral for *user_id* or None."""
    stmt = (
        select(Referral.landlord_id)
        .where(Referral.user_id == user_id)
        .order_by(Referral.ts.desc())
        .limit(1)
    )
    return await sess.scalar(stmt)


async def _chosen_commission(
    sess: SessionDep, landlord_id: int | None, tour_id: int, max_commission: Decimal
) -> Decimal:
    """Return commission_pct chosen by *landlord* for *tour* (or 0 if none).

    Ensures it does not exceed *max_commission*.
    """
    if landlord_id is None:
        return Decimal("0")

    stmt = select(LandlordCommission.commission_pct).where(
        LandlordCommission.landlord_id == landlord_id,
        LandlordCommission.tour_id == tour_id,
    )
    pct: Decimal | None = await sess.scalar(stmt)
    if pct is None:
        return Decimal("0")
    return min(pct, max_commission)


def _discounted_price(
    raw_price: Decimal, max_commission: Decimal, chosen_commission: Decimal
) -> Decimal:
    """Return price applying discount given *max* and *chosen* commission."""
    discount_pct = (max_commission - chosen_commission).quantize(Decimal("0.01"))
    if discount_pct < 0:
        discount_pct = Decimal("0")
    return (raw_price * (HUNDRED - discount_pct) / HUNDRED).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
#  New End-points required by the Telegram tourist flow
# ---------------------------------------------------------------------------


@router.get("/tours/search", summary="Search tours with filters and return discounted price")
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
    """Return lightweight tour list respecting filters and discounted price.

    – If *city* provided, match tours that have at least one Departure linked to
      an Apartment in that city (via landlord referral).  For MVP we fall back
      to filtering by city *of the last scanned apartment* because Tour has no
      location columns yet.
    """

    # Determine landlord associated to tourist (may be None → no discount)
    landlord_id = None
    if user and "sub" in user:
        landlord_id = await _last_referral_landlord_id(sess, int(user["sub"]))

    # Base query: Tours + optional joins for filters
    stmt = select(Tour)

    # Price filters (raw list price)
    if price_min is not None:
        stmt = stmt.where(Tour.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Tour.price <= price_max)

    # Date range – need to join departures
    if date_from or date_to:
        stmt = stmt.join(Departure, Departure.tour_id == Tour.id)
        if date_from:
            stmt = stmt.where(Departure.starts_at >= date_from)
        if date_to:
            stmt = stmt.where(Departure.starts_at <= date_to)

    # Duration filters (minutes)
    if duration_min is not None:
        stmt = stmt.where(Tour.duration_minutes >= duration_min)
    if duration_max is not None:
        stmt = stmt.where(Tour.duration_minutes <= duration_max)

    # City filter via City table if provided
    if city is not None:
        stmt = stmt.join(City, City.id == Tour.city_id)
        stmt = stmt.where(func.lower(City.name) == city.lower())

    # Additional fallback: if user has landlord referral but tour city missing, we already narrowed by departure/apartment earlier.

    stmt = stmt.order_by(Tour.id.desc()).limit(limit).offset(offset)

    tours: Sequence[Tour] = (await sess.scalars(stmt)).unique().all()

    out: List[dict] = []
    for t in tours:
        chosen_comm = await _chosen_commission(sess, landlord_id, t.id, t.max_commission_pct)
        price_net = _discounted_price(t.price, t.max_commission_pct, chosen_comm)
        out.append(
            {
                "id": t.id,
                "title": t.title,
                "price_raw": str(t.price),
                "price_net": str(price_net),
                "category": t.category.name if t.category is not None else None,
            }
        )
    return out


@router.get(
    "/tours/{tour_id}/categories",
    summary="List ticket categories including discounted price",
)
async def tour_categories(tour_id: int, sess: SessionDep, user: dict | None = Depends(lambda: None)):
    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour:
        raise HTTPException(404, "Tour not found")

    landlord_id = None
    chosen_comm = None
    if user and "sub" in user:
        landlord_id = await _last_referral_landlord_id(sess, int(user["sub"]))
        chosen_comm = await _chosen_commission(sess, landlord_id, tour_id, tour.max_commission_pct)

    categories = (
        await sess.scalars(select(TicketCategory).where(TicketCategory.tour_id == tour_id))
    ).all()

    out: List[dict] = []
    for c in categories:
        if chosen_comm is not None:
            net = _discounted_price(c.price, tour.max_commission_pct, chosen_comm)
        else:
            net = c.price
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "price_raw": str(c.price),
                "price_net": str(net),
            }
        )
    return out


class QuoteItem(BaseModel):
    category_id: int
    qty: int = Field(gt=0)

class QuoteIn(BaseModel):
    departure_id: int
    items: list[QuoteItem]

class QuoteOut(BaseModel):
    total_net: Decimal
    seats_left: int

@router.post(
    "/quote",
    response_model=QuoteOut,
    summary="Preview price and availability before confirming booking",
    dependencies=[Depends(role_required("bot_user"))],
)
async def price_quote(payload: QuoteIn, sess: SessionDep, user=Depends(current_user)):
    dep: Departure | None = await sess.get(Departure, payload.departure_id)
    if not dep:
        raise HTTPException(404, "Departure not found")

    # Capacity check
    taken_stmt = select(func.coalesce(func.sum(Purchase.qty), 0)).where(Purchase.departure_id == dep.id)
    taken: int = await sess.scalar(taken_stmt) or 0
    remaining = dep.capacity - taken

    # Discount calculation – explicitly load Tour to avoid implicit I/O
    tour: Tour | None = await sess.get(Tour, dep.tour_id)
    if tour is None:
        raise HTTPException(404, "Tour not found")

    landlord_id = await _last_referral_landlord_id(sess, int(user["sub"]))
    chosen_comm = await _chosen_commission(sess, landlord_id, tour.id, tour.max_commission_pct)

    # Fetch categories map
    cats = (
        await sess.scalars(select(TicketCategory).where(TicketCategory.tour_id == dep.tour_id))
    ).all()
    cat_map = {c.id: c for c in cats}

    total_net = Decimal("0")
    for it in payload.items:
        cat = cat_map.get(it.category_id)
        if not cat:
            raise HTTPException(400, "Invalid category id")
        net_price = _discounted_price(cat.price, tour.max_commission_pct, chosen_comm)
        total_net += net_price * it.qty

    return QuoteOut(total_net=total_net.quantize(Decimal("0.01")), seats_left=max(remaining, 0))


@router.get(
    "/tours/{tour_id}/departures",
    summary="Upcoming departures for a given tour (with seats left)",
)
async def tour_departures(
    tour_id: int,
    sess: SessionDep,
    limit: int = Query(30, gt=0, le=100),
    offset: int = Query(0, ge=0),
):
    """Return next departures for *tour_id* capped by *limit*.

    Response shape::
        [{"id": 123, "starts_at": "2025-06-01T09:00:00Z", "capacity": 25, "seats_left": 12}]
    """
    from datetime import datetime
    from sqlalchemy import select
    from .bookings import _seats_taken  # local util (avoids duplication)

    now = datetime.utcnow()

    stmt = (
        select(Departure)
        .where(Departure.tour_id == tour_id, Departure.starts_at >= now)
        .order_by(Departure.starts_at)
        .limit(limit)
        .offset(offset)
    )
    deps = (await sess.scalars(stmt)).all()

    out = []
    for dep in deps:
        taken = await _seats_taken(sess, dep.id)
        out.append(
            {
                "id": dep.id,
                "starts_at": dep.starts_at.isoformat() if dep.starts_at else None,
                "capacity": dep.capacity,
                "seats_left": max(dep.capacity - taken, 0),
            }
        )
    return out


@router.get("/cities", response_model=list[dict])
async def list_cities(sess: SessionDep):
    """Return all cities for dropdown selection."""
    stmt = select(City.id, City.name).order_by(City.name)
    result = await sess.execute(stmt)
    return [{"id": id, "name": name} for id, name in result]


@router.get("/tour_categories", response_model=list[dict])
async def list_tour_categories(sess: SessionDep):
    """Return all tour categories for dropdown selection."""
    stmt = select(TourCategory.id, TourCategory.name).order_by(TourCategory.name)
    result = await sess.execute(stmt)
    return [{"id": id, "name": name} for id, name in result]


@router.get("/ticket_classes", response_model=list[dict])
async def list_ticket_classes(sess: SessionDep):
    """Return all ticket classes for dropdown selection."""
    stmt = select(TicketClass.id, TicketClass.code, TicketClass.human_name).order_by(TicketClass.human_name)
    result = await sess.execute(stmt)
    return [{"id": id, "code": code, "name": name} for id, code, name in result]


# ---------------------------------------------------------------------------
#  Basic public endpoints (lightweight list and detail)
# ---------------------------------------------------------------------------

@router.get("/tours", summary="List tours (lightweight)")
async def list_tours(
    sess: SessionDep,
    limit: int = Query(100, gt=0, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Tour.id, Tour.title).order_by(Tour.id.desc()).limit(limit).offset(offset)
    result = await sess.execute(stmt)
    return [{"id": tid, "title": title} for tid, title in result]


@router.get("/tours/{tid}", summary="Full tour detail")
async def tour_detail(tid: int, sess: SessionDep):
    stmt = (
        select(Tour)
        .options(selectinload(Tour.images))
        .where(Tour.id == tid)
    )
    tour = await sess.scalar(stmt)
    if not tour:
        raise HTTPException(404, "Tour not found")

    return {
        "id": tour.id,
        "title": tour.title,
        "description": tour.description,
        "price": str(tour.price),
        "category": tour.category.name if tour.category is not None else None,
        "images": [presigned(img.key) for img in tour.images],
    }


@router.get("/departures/{departure_id}/availability", summary="Seats left for a departure")
async def departure_availability(departure_id: int, sess: SessionDep):
    """Return number of free seats for the given departure."""

    dep: Departure | None = await sess.get(Departure, departure_id)
    if not dep:
        raise HTTPException(404, "Departure not found")

    taken_stmt = select(func.coalesce(func.sum(Purchase.qty), 0)).where(Purchase.departure_id == departure_id)
    taken: int | None = await sess.scalar(taken_stmt)
    taken = taken or 0
    remaining = max(dep.capacity - taken, 0)

    return {"remaining": remaining} 