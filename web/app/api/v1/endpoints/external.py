"""External API endpoints for API key authenticated operations."""

from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse
import csv
from io import StringIO

from ....deps import SessionDep
from ....models import ApiKey
from ....security import require_api_key
from ....services.external_service import ExternalService
from ....core.exceptions import NotFoundError, ConflictError
from ..schemas.external_schemas import CapacityBody, CapacityOut, BookingExportItem

router = APIRouter(prefix="/external", tags=["external"])


def _get_agency_id_from_key(api_key_row: ApiKey) -> int:
    """Extract agency ID from API key row."""
    return api_key_row.agency_id


@router.patch("/departures/{dep_id}/capacity", response_model=CapacityOut)
async def ext_set_capacity(
    sess: SessionDep,
    dep_id: int = Path(..., gt=0),
    body: CapacityBody | None = None,
    api_key_row: ApiKey = Depends(require_api_key),
):
    """Update departure capacity."""
    if body is None:
        raise HTTPException(400, "Empty payload")
    
    agency_id = _get_agency_id_from_key(api_key_row)
    service = ExternalService(sess)
    
    try:
        result = await service.update_departure_capacity(agency_id, dep_id, body.capacity)
        return CapacityOut(**result)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/bookings")
async def ext_export_bookings(
    sess: SessionDep,
    request: Request,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    format: str | None = Query(None, pattern="^(json|csv)$"),
    api_key_row: ApiKey = Depends(require_api_key),
):
    """Export bookings in JSON or CSV format."""
    agency_id = _get_agency_id_from_key(api_key_row)
    service = ExternalService(sess)
    
    bookings = await service.export_bookings(agency_id, from_date, to_date)
    
    # Determine format from query param or Accept header
    wants_csv = (
        format == "csv" or 
        (format is None and "text/csv" in request.headers.get("accept", "").lower())
    )
    
    if wants_csv:
        # Generate CSV
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(["booking_id", "departure_id", "starts_at", "tour_title", "qty", "net_price"])
        for booking in bookings:
            w.writerow([
                booking["booking_id"],
                booking["departure_id"],
                booking["starts_at"] or "",
                booking["tour_title"],
                booking["qty"],
                booking["net_price"],
            ])
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=bookings.csv"}
        )
    
    # Return JSON
    return {"bookings": bookings} 