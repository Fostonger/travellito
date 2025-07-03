from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
import io
import csv

from app.api.v1.schemas.booking_schemas import (
    BookingStatusUpdate, BookingOut, BookingExportOut, BookingMetrics
)
from app.deps import SessionDep
from app.security import current_user
from app.services.booking_service import BookingService
from app.core import BaseError


router = APIRouter()


def get_agency_id(user: dict) -> int:
    """Extract agency ID from user token"""
    agency_id = user.get("agency_id")
    if not agency_id:
        raise BaseError("No agency associated with user", status_code=403)
    return int(agency_id)


@router.get("/", response_model=List[BookingExportOut])
async def list_bookings(
    sess: SessionDep,
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD) inclusive"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD) inclusive"),
    format: Optional[str] = Query(None, enum=["json", "csv"], description="Response format"),
    user=Depends(current_user),
):
    """List bookings with optional date filtering and export format"""
    agency_id = get_agency_id(user)
    service = BookingService(sess)
    
    # Get bookings data
    bookings_data = await service.export_bookings(
        agency_id=agency_id,
        from_date=from_date,
        to_date=to_date,
        format=format or "json"
    )
    
    # Return CSV if requested
    if format == "csv":
        output = io.StringIO()
        if bookings_data:
            # Create CSV with all fields except categories (too complex for CSV)
            fieldnames = [k for k in bookings_data[0].keys() if k != "categories"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            
            for booking in bookings_data:
                row = {k: v for k, v in booking.items() if k != "categories"}
                writer.writerow(row)
        
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=bookings.csv"}
        )
    
    # Return JSON
    return bookings_data


@router.get("/metrics", response_model=BookingMetrics)
async def get_booking_metrics(
    sess: SessionDep,
    user=Depends(current_user),
):
    """Get booking metrics for agency dashboard"""
    agency_id = get_agency_id(user)
    service = BookingService(sess)
    
    metrics = await service.get_booking_metrics(agency_id)
    return BookingMetrics(**metrics)


@router.patch("/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    payload: BookingStatusUpdate,
    sess: SessionDep,
    user=Depends(current_user),
):
    """Update booking status (confirm or reject)"""
    agency_id = get_agency_id(user)
    service = BookingService(sess)
    
    booking = await service.update_booking_status(
        booking_id=booking_id,
        agency_id=agency_id,
        status=payload.status
    )
    
    await sess.commit()
    
    # TODO: Send notification to tourist about status change
    
    return {"success": True, "booking_id": booking.id, "status": booking.status} 