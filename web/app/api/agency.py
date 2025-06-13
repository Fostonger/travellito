from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Path, status, UploadFile, File, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from ..deps import SessionDep
from ..models import Tour, TourImage, Departure, Purchase, TicketCategory, User
from ..security import current_user, role_required
from ..storage import upload_image, presigned


router = APIRouter(
    prefix="/agency",
    tags=["agency"],
    dependencies=[Depends(role_required("agency"))],
)


# ---------------------------------------------------------------------------
#  Schemas
# ---------------------------------------------------------------------------


class TourIn(BaseModel):
    title: str
    description: str | None = None
    price: Decimal = Field(..., gt=0)
    duration_minutes: int | None = Field(None, gt=0)
    city: str | None = Field(None, max_length=64)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)


class TourOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    price: Decimal

    model_config = {
        "from_attributes": True,
    }


class ImagesOut(BaseModel):
    keys: list[str]
    urls: list[str]


# ---------------------------------------------------------------------------
#  Departure Schemas
# ---------------------------------------------------------------------------


from datetime import datetime


class DepartureIn(BaseModel):
    tour_id: int = Field(..., gt=0)
    starts_at: datetime
    capacity: int = Field(..., gt=0)


class DepartureUpdate(BaseModel):
    starts_at: datetime | None = None
    capacity: int | None = Field(None, gt=0)


class DepartureOut(BaseModel):
    id: int
    tour_id: int
    starts_at: datetime
    capacity: int

    model_config = {
        "from_attributes": True,
    }


# ---------------------------------------------------------------------------
#  Departure helpers
# ---------------------------------------------------------------------------


async def _seats_taken(sess: SessionDep, departure_id: int) -> int:
    stmt = select(func.coalesce(func.sum(Purchase.qty), 0)).where(Purchase.departure_id == departure_id)
    taken: int | None = await sess.scalar(stmt)
    return taken or 0


# ---------------------------------------------------------------------------
#  Departure Endpoints
# ---------------------------------------------------------------------------


@router.get("/departures", response_model=list[DepartureOut])
async def list_departures(
    sess: SessionDep,
    tour: int | None = None,
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    """List departures for the agency. Optional filter by *tour* id."""

    agency_id = _get_agency_id(user)

    stmt = (
        select(Departure)
        .join(Tour, Departure.tour_id == Tour.id)
        .where(Tour.agency_id == agency_id)
    )
    if tour:
        stmt = stmt.where(Departure.tour_id == tour)

    stmt = stmt.order_by(Departure.starts_at).limit(limit).offset(offset)
    result = (await sess.scalars(stmt)).all()
    return [DepartureOut.from_orm(d) for d in result]


@router.post("/departures", response_model=DepartureOut, status_code=status.HTTP_201_CREATED)
async def create_departure(
    payload: DepartureIn,
    sess: SessionDep,
    user=Depends(current_user),
):
    agency_id = _get_agency_id(user)

    # Validate that tour exists and belongs to agency
    tour: Tour | None = await sess.get(Tour, payload.tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    dep = Departure(
        tour_id=payload.tour_id,
        starts_at=payload.starts_at,
        capacity=payload.capacity,
    )
    sess.add(dep)
    await sess.flush()
    await sess.commit()

    return DepartureOut.from_orm(dep)


@router.patch("/departures/{dep_id}", response_model=DepartureOut)
async def update_departure(
    sess: SessionDep,
    dep_id: int = Path(..., gt=0),
    payload: DepartureUpdate | dict | None = None,
    user=Depends(current_user),
):
    if payload is None:
        raise HTTPException(400, "Empty payload")

    agency_id = _get_agency_id(user)

    # ------------------------------------------------------------------
    #  Acquire exclusive lock on the departure row so that no concurrent
    #  tourist-booking transaction can read / modify it until we commit.
    # ------------------------------------------------------------------
    stmt_dep = (
        select(Departure)
        .where(Departure.id == dep_id)
        .with_for_update()
    )

    dep: Departure | None = await sess.scalar(stmt_dep)
    if not dep:
        raise HTTPException(404, "Departure not found")

    # Fetch related tour to assert the departure belongs to the requesting
    # agency *after* we hold the lock so we avoid TOCTOU issues.
    tour: Tour | None = await sess.get(Tour, dep.tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Departure not found")

    data = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)

    # --------------------------------------------------------------
    #  Capacity validation – we can safely compute *taken* now that
    #  we hold the FOR UPDATE lock, guaranteeing a consistent view.
    # --------------------------------------------------------------
    if "capacity" in data and data["capacity"] is not None:
        new_cap = int(data["capacity"])
        taken = await _seats_taken(sess, dep.id)
        if new_cap < taken:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Capacity lower than already booked seats")
        dep.capacity = new_cap

    if "starts_at" in data and data["starts_at"] is not None:
        dep.starts_at = data["starts_at"]

    await sess.commit()
    return DepartureOut.from_orm(dep)


class CapacityBody(BaseModel):
    capacity: int = Field(..., gt=0)


@router.patch("/departures/{dep_id}/capacity", response_model=DepartureOut)
async def set_capacity(
    sess: SessionDep,
    dep_id: int = Path(..., gt=0),
    body: CapacityBody | None = None,
    user=Depends(current_user),
):
    if body is None:
        raise HTTPException(400, "Empty payload")

    return await update_departure(sess, dep_id, DepartureUpdate(capacity=body.capacity), user)


# ---------------------------------------------------------------------------
#  Endpoints – CRUD Tours
# ---------------------------------------------------------------------------


@router.get("/tours", response_model=list[TourOut])
async def list_tours(
    sess: SessionDep,
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    """Return tours owned by the agency bound to the JWT."""

    agency_id = _get_agency_id(user)

    stmt = (
        select(Tour)
        .where(Tour.agency_id == agency_id)
        .order_by(Tour.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result: Sequence[Tour] = (await sess.scalars(stmt)).all()

    return [TourOut.from_orm(t) for t in result]


@router.post("/tours", response_model=TourOut, status_code=status.HTTP_201_CREATED)
async def create_tour(payload: TourIn, sess: SessionDep, user=Depends(current_user)):
    agency_id = _get_agency_id(user)

    tour = Tour(
        agency_id=agency_id,
        title=payload.title,
        description=payload.description,
        price=payload.price,
        duration_minutes=payload.duration_minutes,
        city=payload.city,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    sess.add(tour)
    await sess.flush()
    await sess.commit()

    return TourOut.from_orm(tour)


@router.patch("/tours/{tour_id}", response_model=TourOut)
async def update_tour(
    sess: SessionDep,
    tour_id: int = Path(..., gt=0),
    payload: TourIn | dict | None = None,
    user=Depends(current_user),
):
    agency_id = _get_agency_id(user)

    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    if payload is None:
        raise HTTPException(400, "Empty payload")

    data = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)

    for field, value in data.items():
        if value is not None:
            setattr(tour, field, value)

    await sess.commit()

    return TourOut.from_orm(tour)


@router.delete("/tours/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tour(
    sess: SessionDep,
    tour_id: int = Path(..., gt=0),
    user=Depends(current_user),
):
    agency_id = _get_agency_id(user)

    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    await sess.delete(tour)
    await sess.commit()

    return None  # 204


# ---------------------------------------------------------------------------
#  Images upload
# ---------------------------------------------------------------------------


@router.post("/tours/{tour_id}/images", response_model=ImagesOut, status_code=status.HTTP_201_CREATED)
async def upload_tour_images(
    sess: SessionDep,
    tour_id: int = Path(..., gt=0),
    files: list[UploadFile] = File(...),
    user=Depends(current_user),
):
    """Upload one or multiple images and link them to the tour.

    Each file is uploaded via MinIO/S3 and a TourImage row is created.
    Returns the object keys and short-lived presigned URLs for immediate preview
    in the admin UI.
    """

    if not files:
        raise HTTPException(400, "No files uploaded")

    agency_id = _get_agency_id(user)

    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    keys: list[str] = []
    for f in files:
        key = upload_image(f)
        keys.append(key)
        sess.add(TourImage(tour_id=tour.id, key=key))

    await sess.commit()

    urls = [presigned(k) for k in keys]

    return ImagesOut(keys=keys, urls=urls)


# ---------------------------------------------------------------------------
#  TicketCategory schemas & endpoints
# ---------------------------------------------------------------------------


class CategoryIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    price: Decimal = Field(..., gt=0)


class CategoryOut(BaseModel):
    id: int
    name: str
    price: Decimal

    model_config = {
        "from_attributes": True,
    }


@router.get("/tours/{tour_id}/categories", response_model=list[CategoryOut])
async def list_categories(
    tour_id: int,
    sess: SessionDep,
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    agency_id = _get_agency_id(user)
    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    stmt = select(TicketCategory).where(TicketCategory.tour_id == tour_id).order_by(TicketCategory.id).limit(limit).offset(offset)
    result = (await sess.scalars(stmt)).all()
    return [CategoryOut.from_orm(c) for c in result]


@router.post("/tours/{tour_id}/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def add_category(tour_id: int, payload: CategoryIn, sess: SessionDep, user=Depends(current_user)):
    agency_id = _get_agency_id(user)
    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    cat = TicketCategory(tour_id=tour_id, name=payload.name, price=payload.price)
    sess.add(cat)
    await sess.flush()
    await sess.commit()

    return CategoryOut.from_orm(cat)


@router.patch("/tours/{tour_id}/categories/{cat_id}", response_model=CategoryOut)
async def update_category(tour_id: int, cat_id: int, 
                          sess: SessionDep,
                          payload: CategoryIn | dict | None = None,
                          user=Depends(current_user)):
    if payload is None:
        raise HTTPException(400, "Empty payload")

    agency_id = _get_agency_id(user)
    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    cat: TicketCategory | None = await sess.get(TicketCategory, cat_id)
    if not cat or cat.tour_id != tour_id:
        raise HTTPException(404, "Category not found")

    data = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)

    for f, v in data.items():
        if v is not None:
            setattr(cat, f, v)

    await sess.commit()
    return CategoryOut.from_orm(cat)


@router.delete("/tours/{tour_id}/categories/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(tour_id: int, cat_id: int, sess: SessionDep, user=Depends(current_user)):
    agency_id = _get_agency_id(user)
    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Tour not found")

    cat: TicketCategory | None = await sess.get(TicketCategory, cat_id)
    if not cat or cat.tour_id != tour_id:
        raise HTTPException(404, "Category not found")

    await sess.delete(cat)
    await sess.commit()
    return None


# ---------------------------------------------------------------------------
#  Bookings export (CSV)
# ---------------------------------------------------------------------------

from fastapi.responses import StreamingResponse
import csv
from io import StringIO
from datetime import date, datetime, timezone


@router.get("/bookings", summary="List / export bookings")
async def export_bookings(
    sess: SessionDep,
    request: Request,
    from_date: date | None = Query(None, description="Start date (YYYY-MM-DD) inclusive"),
    to_date: date | None = Query(None, description="End date (YYYY-MM-DD) inclusive"),
    format: str | None = Query(None, enum=["json", "csv"], description="Response format: json (default) or csv"),
    user=Depends(current_user),
):
    """Return bookings as JSON (default) or CSV when format=csv or Accept header asks for text/csv."""

    agency_id = _get_agency_id(user)

    # Build base query joining the necessary tables
    stmt = (
        select(
            Purchase.id,
            Purchase.ts,
            Purchase.qty,
            Purchase.amount,          # net price
            Purchase.amount_gross,
            Purchase.commission_pct,
            Departure.id.label("dep_id"),
            Departure.starts_at,
            Tour.title,
            User.first,
            User.last,
            User.username,
            User.phone,
        )
        .join(Departure, Departure.id == Purchase.departure_id)
        .join(Tour, Tour.id == Departure.tour_id)
        .join(User, User.id == Purchase.user_id)
        .where(Tour.agency_id == agency_id)
        .order_by(Purchase.ts.desc())
    )

    # Apply optional date filters on purchase timestamp (UTC)
    if from_date:
        start_dt = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
        stmt = stmt.where(Purchase.ts >= start_dt)
    if to_date:
        end_dt = datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc)
        stmt = stmt.where(Purchase.ts <= end_dt)

    rows = (await sess.execute(stmt)).all()

    # Prepare data rows in unified structure
    data_rows: list[tuple] = []
    for (
        bid,
        ts,
        qty,
        amount,   # net
        amount_gross,
        commission_pct,
        dep_id,
        starts_at,
        title,
        first,
        last,
        username,
        phone,
    ) in rows:
        full_name = " ".join(filter(None, [first, last])) or (username or "")
        commission_pct = commission_pct or 0
        commission_amount = (amount_gross * commission_pct / 100) if amount_gross is not None else 0
        data_rows.append((
            bid,
            dep_id,
            starts_at,
            title,
            full_name,
            phone,
            qty,
            amount,
            amount_gross,
            commission_pct,
            commission_amount,
            ts,
        ))

    wants_csv = (
        (format == "csv") or
        (format is None and "text/csv" in request.headers.get("accept", "").lower())
    )

    if wants_csv:
        # Build CSV in-memory
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "booking_id",
            "departure_id",
            "starts_at",
            "tour_title",
            "tourist_name",
            "tourist_phone",
            "qty",
            "net_price",
            "gross_price",
            "commission_pct",
            "commission_amount",
            "booked_at",
        ])

        for (
            bid,
            dep_id,
            starts_at,
            title,
            full_name,
            phone,
            qty,
            amount,
            amount_gross,
            commission_pct,
            commission_amount,
            ts,
        ) in data_rows:
            writer.writerow([
                bid,
                dep_id,
                starts_at.isoformat() if starts_at else "",
                title,
                full_name,
                phone or "",
                qty,
                str(amount),
                str(amount_gross),
                str(commission_pct),
                str(commission_amount),
                ts.isoformat() if ts else "",
            ])

        buffer.seek(0)

        filename_parts = [
            "bookings",
            from_date.isoformat() if from_date else "",
            to_date.isoformat() if to_date else "",
        ]
        filename = "_".join(filter(None, filename_parts)) + ".csv"

        return StreamingResponse(buffer, media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename={filename}",
        })

    # JSON output
    return {
        "bookings": [
            {
                "booking_id": bid,
                "departure_id": dep_id,
                "starts_at": starts_at.isoformat() if starts_at else None,
                "tour_title": title,
                "tourist_name": full_name,
                "tourist_phone": phone or "",
                "qty": qty,
                "net_price": str(amount),
                "gross_price": str(amount_gross),
                "commission_pct": str(commission_pct),
                "commission_amount": str(commission_amount),
                "booked_at": ts.isoformat() if ts else None,
            }
            for (
                bid,
                dep_id,
                starts_at,
                title,
                full_name,
                phone,
                qty,
                amount,
                amount_gross,
                commission_pct,
                commission_amount,
                ts,
            ) in data_rows
        ]
    }


def _get_agency_id(user: dict) -> int:
    """Return the agency id encoded in the JWT *sub* claim.

    For MVP we assume the token was minted with sub = agency_id. In the future
    we may store agency_id as a dedicated claim.
    """

    try:
        return int(user["sub"])
    except (KeyError, ValueError):  # pragma: no cover
        raise HTTPException(401, "Invalid agency token") 