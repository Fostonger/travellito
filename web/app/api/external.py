from __future__ import annotations

"""External API for agencies authenticated with X-API-Key.

Currently supports:
    PATCH /external/departures/{id}/capacity
    GET   /external/bookings

The logic mirrors the regular /agency endpoints but is authorised via ApiKey
instead of JWT.  The ApiKey row encodes the `agency_id` we operate on.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy import select
from pydantic import BaseModel, Field

from ..deps import SessionDep
from ..models import Departure, Tour, Purchase, ApiKey
from ..security import require_api_key

router = APIRouter(prefix="/external", tags=["external"])  # included by api.__init__

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_agency_id_from_key(api_key_row: ApiKey) -> int:
    return api_key_row.agency_id

# ---------------------------------------------------------------------------
#  Capacity PATCH (mirrors /agency)
# ---------------------------------------------------------------------------

class CapacityBody(BaseModel):
    capacity: int = Field(..., gt=0)


@router.patch("/departures/{dep_id}/capacity", response_model=dict)
async def ext_set_capacity(
    sess: SessionDep,
    dep_id: int = Path(..., gt=0),
    body: CapacityBody | None = None,
    api_key_row: ApiKey = Depends(require_api_key),
):
    if body is None:
        raise HTTPException(400, "Empty payload")

    agency_id = _get_agency_id_from_key(api_key_row)

    # Lock departure row
    stmt_dep = select(Departure).where(Departure.id == dep_id).with_for_update()
    dep: Departure | None = await sess.scalar(stmt_dep)
    if not dep:
        raise HTTPException(404, "Departure not found")

    tour: Tour | None = await sess.get(Tour, dep.tour_id)
    if not tour or tour.agency_id != agency_id:
        raise HTTPException(404, "Departure not found")

    new_cap = body.capacity
    # Ensure new capacity is not below already taken seats
    taken_stmt = (
        select(Purchase.qty).where(Purchase.departure_id == dep.id)
    )
    taken_rows: Sequence[int] = (await sess.scalars(taken_stmt)).all()
    taken = sum(taken_rows) if taken_rows else 0
    if new_cap < taken:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Capacity lower than booked seats")

    dep.capacity = new_cap
    await sess.commit()

    return {"id": dep.id, "capacity": dep.capacity}

# ---------------------------------------------------------------------------
#  Bookings export (CSV or JSON) – reuses logic from agency.py
# ---------------------------------------------------------------------------

from fastapi.responses import StreamingResponse
import csv
from io import StringIO


@router.get("/bookings")
async def ext_export_bookings(
    sess: SessionDep,
    request: Request,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    format: str | None = Query(None, enum=["json", "csv"]),
    api_key_row: ApiKey = Depends(require_api_key),
):
    agency_id = _get_agency_id_from_key(api_key_row)

    stmt = (
        select(
            Purchase.id,
            Purchase.ts,
            Purchase.qty,
            Purchase.amount,          # net
            Purchase.amount_gross,
            Purchase.commission_pct,
            Departure.id.label("dep_id"),
            Departure.starts_at,
            Tour.title,
        )
        .join(Departure, Departure.id == Purchase.departure_id)
        .join(Tour, Tour.id == Departure.tour_id)
        .where(Tour.agency_id == agency_id)
        .order_by(Purchase.ts.desc())
    )

    # Date filters
    if from_date:
        stmt = stmt.where(Purchase.ts >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc))
    if to_date:
        stmt = stmt.where(Purchase.ts <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc))

    rows = (await sess.execute(stmt)).all()

    wants_csv = (
        format == "csv" or (format is None and "text/csv" in request.headers.get("accept", "").lower())
    )

    if wants_csv:
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["booking_id", "departure_id", "starts_at", "tour_title", "qty", "net_price"])
        for bid, ts, qty, amount, amount_gross, pct, dep_id, starts, title in rows:
            w.writerow([bid, dep_id, starts.isoformat() if starts else "", title, qty, str(amount)])
        buf.seek(0)
        return StreamingResponse(buf, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=bookings.csv"})

    # JSON output
    return {
        "bookings": [
            {
                "booking_id": bid,
                "departure_id": dep_id,
                "starts_at": starts.isoformat() if starts else None,
                "tour_title": title,
                "qty": qty,
                "net_price": str(amount),
            }
            for bid, ts, qty, amount, amount_gross, pct, dep_id, starts, title in rows
        ]
    } 