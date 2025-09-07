from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
import io
import csv
import json

from app.api.v1.schemas.booking_schemas import (
    BookingStatusUpdate, BookingOut, BookingExportOut, BookingMetrics,
    TouristBookingOut
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
    request: Request,
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) inclusive"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD) inclusive"),
    format: Optional[str] = Query(None, enum=["json", "csv"], description="Response format"),
    user=Depends(current_user),
):
    """List bookings with optional date filtering and export format"""
    try:
        agency_id = get_agency_id(user)
        service = BookingService(sess)
        
        # Parse date parameters
        from_date_obj = None
        to_date_obj = None
        
        if from_date:
            try:
                from_date_obj = date.fromisoformat(from_date)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid from_date format. Use YYYY-MM-DD"}
                )
        
        if to_date:
            try:
                to_date_obj = date.fromisoformat(to_date)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid to_date format. Use YYYY-MM-DD"}
                )
        
        # Get bookings data
        bookings_data = await service.export_bookings(
            agency_id=agency_id,
            from_date=from_date_obj,
            to_date=to_date_obj,
            format=format or "json"
        )
        
        # Add timezone offset from the tour's city
        # We need to fetch this information separately to avoid modifying the service
        from app.models import Purchase, Departure, Tour, City
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        
        # Get all booking IDs from the exported data
        booking_ids = [b["booking_id"] for b in bookings_data]
        
        if booking_ids:
            # Fetch purchases with city timezone info
            query = (
                select(Purchase)
                .options(
                    selectinload(Purchase.departure)
                    .selectinload(Departure.tour)
                    .selectinload(Tour.city)
                )
                .where(Purchase.id.in_(booking_ids))
            )
            result = await sess.execute(query)
            purchases_with_city = {p.id: p for p in result.scalars().all()}
            
            # Add timezone offset to each booking
            for booking in bookings_data:
                purchase = purchases_with_city.get(booking["booking_id"])
                if purchase and purchase.departure and purchase.departure.tour and purchase.departure.tour.city:
                    booking["timezone_offset_min"] = purchase.departure.tour.city.timezone_offset_min or 0
                else:
                    booking["timezone_offset_min"] = 0
        
        # Add missing fields required by schema
        for booking in bookings_data:
            if "commission_percent" not in booking:
                booking["commission_percent"] = 0.0
            if "commission_amount" not in booking:
                booking["commission_amount"] = 0.0
        
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
    except BaseError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": e.message}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "type": str(type(e))}
        )


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
    request: Request,
    user=Depends(current_user),
):
    """Update booking status (confirm or reject)"""
    try:
        agency_id = get_agency_id(user)
        service = BookingService(sess)
        
        # Extract client ID for analytics tracking
        client_id = getattr(request.state, "client_id", None)
        
        booking = await service.update_booking_status(
            booking_id=booking_id,
            agency_id=agency_id,
            status=payload.status,
            client_id=client_id
        )
        
        await sess.commit()
        
        # TODO: Send notification to tourist about status change
        
        return {"success": True, "booking_id": booking.id, "status": booking.status}
    except BaseError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": e.message}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# Tourist booking endpoints
@router.get("/tourist", response_model=List[TouristBookingOut])
async def list_tourist_bookings(
    sess: SessionDep,
    user=Depends(current_user),
):
    """List all bookings for the current tourist user"""
    try:
        user_id = int(user["sub"])
        service = BookingService(sess)
        
        bookings = await service.get_tourist_bookings(user_id)
        return bookings
    except BaseError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": e.message}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.patch("/tourist/{booking_id}/cancel")
async def cancel_tourist_booking(
    booking_id: int,
    sess: SessionDep,
    request: Request,
    user=Depends(current_user),
):
    """Cancel a booking as a tourist"""
    try:
        service = BookingService(sess)
        user_id = int(user["sub"])
        
        # Extract client ID for analytics tracking
        client_id = getattr(request.state, "client_id", None)
        
        result = await service.cancel_tourist_booking(
            booking_id=booking_id,
            user_id=user_id,
            client_id=client_id
        )
        
        if result:
            return {"message": "Booking cancelled successfully"}
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Failed to cancel booking"}
            )
    except BaseError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": e.message, "details": e.details}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        ) 