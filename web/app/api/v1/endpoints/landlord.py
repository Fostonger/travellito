"""Landlord endpoints."""

from __future__ import annotations

import io
import csv
import os
from urllib.parse import quote_plus, quote
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, status, Query, Response
from fastapi.responses import Response as FastAPIResponse
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ....deps import SessionDep
from ....security import current_user, role_required
from ....services.landlord_service import LandlordService
from ....core.exceptions import NotFoundError, ValidationError
from ..schemas.landlord_schemas import (
    ApartmentIn,
    ApartmentOut,
    CommissionBody,
    CommissionOut,
    TourForLandlord,
    EarningsOut,
)

# QR code generation imports
try:
    import qrcode
    from qrcode.image.pil import PilImage
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    HAS_QR_SUPPORT = True
except ImportError:
    HAS_QR_SUPPORT = False

router = APIRouter(
    tags=["landlord"],
    dependencies=[Depends(role_required("landlord"))],
)

BOT_ALIAS = os.getenv("BOT_ALIAS", "TravellitoBot")


async def _get_landlord_id(sess: SessionDep, user: dict) -> int:
    """Extract landlord ID from user token."""
    try:
        user_id = int(user["sub"])
        service = LandlordService(sess)
        landlord = await service.get_landlord_by_user_id(user_id)
        return landlord.id
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid landlord token")


def _bot_link(payload: str) -> str:
    """Return deep-link for Travellito Telegram bot with payload."""
    return f"https://t.me/{BOT_ALIAS}?start={quote_plus(payload)}"


# Apartment Management
@router.get("/apartments", response_model=list[ApartmentOut])
async def list_apartments(
    sess: SessionDep,
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    """List apartments for the landlord."""
    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    apartments = await service.list_apartments(landlord_id, limit, offset)
    return [ApartmentOut.model_validate(apt) for apt in apartments]


@router.post("/apartments", response_model=ApartmentOut, status_code=status.HTTP_201_CREATED)
async def create_apartment(
    payload: ApartmentIn, sess: SessionDep, user=Depends(current_user)
):
    """Create a new apartment."""
    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    apt = await service.create_apartment(
        landlord_id=landlord_id,
        name=payload.name,
        city_id=payload.city_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return ApartmentOut.model_validate(apt)


@router.patch("/apartments/{apt_id}", response_model=ApartmentOut)
async def update_apartment(
    sess: SessionDep,
    apt_id: int = Path(..., gt=0),
    payload: ApartmentIn | dict | None = None,
    user=Depends(current_user),
):
    """Update an apartment."""
    if payload is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    
    data = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)
    
    try:
        apt = await service.update_apartment(
            landlord_id=landlord_id,
            apt_id=apt_id,
            **data
        )
        return ApartmentOut.model_validate(apt)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# Commission Management
@router.patch("/tours/{tour_id}/commission", response_model=CommissionBody)
async def set_tour_commission(
    sess: SessionDep,
    tour_id: int = Path(..., gt=0),
    body: CommissionBody | None = None,
    user=Depends(current_user),
):
    """Set commission percentage for a tour."""
    if body is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    
    try:
        commission_pct = await service.set_tour_commission(
            landlord_id, tour_id, body.commission_pct
        )
        return CommissionBody(commission_pct=commission_pct)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/commissions", response_model=list[CommissionOut])
async def list_commissions(
    sess: SessionDep,
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    """List all commission settings."""
    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    commissions = await service.list_commissions(landlord_id, limit, offset)
    return [CommissionOut(**comm) for comm in commissions]


@router.get("/tours", response_model=list[TourForLandlord])
async def list_tours_for_commission(
    sess: SessionDep,
    limit: int = Query(100, gt=0, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
):
    """List all tours with commission settings."""
    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    tours = await service.list_tours_with_commission(landlord_id, limit, offset)
    return [TourForLandlord(**tour) for tour in tours]


# Earnings
@router.get("/earnings", response_model=EarningsOut)
async def earnings(
    sess: SessionDep, period: str = "30d", user=Depends(current_user)
):
    """Get earnings statistics."""
    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    
    try:
        earnings_data = await service.get_earnings(landlord_id, period)
        return EarningsOut(**earnings_data)
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/earnings.csv", summary="Download detailed last-30-days earnings as CSV")
async def earnings_csv(sess: SessionDep, user=Depends(current_user)):
    """Export earnings details as CSV."""
    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    
    details = await service.get_earnings_details(landlord_id, days=30)
    
    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["timestamp", "tickets", "amount_net", "commission_pct"])
    
    for detail in details:
        writer.writerow([
            detail["timestamp"],
            detail["tickets"],
            detail["amount_net"],
            detail["commission_pct"],
        ])
    
    csv_bytes = csv_buf.getvalue().encode()
    headers = {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=earnings_last_30d.csv",
    }
    return Response(content=csv_bytes, headers=headers)


# QR Code Generation
@router.get("/apartments/{apt_id}/qr-pdf", response_class=Response,
            summary="Download a single PDF containing one QR code per apartment")
async def apartments_qr_pdf(
    sess: SessionDep,
    apt_id: int = Path(..., gt=0),
    user=Depends(current_user)
):
    """Generate QR codes for all apartments as PDF."""
    if not HAS_QR_SUPPORT:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="QR code generation not available. Install qrcode and reportlab packages."
        )
    
    landlord_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    
    apartments = await service.get_apartments_for_qr(landlord_id, apt_id)
    if not apartments:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No apartments found")
    
    # Mark QR codes as sent
    await service.mark_qr_sent(landlord_id)
    
    # Generate PDF
    buf = io.BytesIO()
    pdf = _canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    # Register a TrueType font that supports Cyrillic characters
    # We'll use DejaVu Sans which has good Unicode support
    # If DejaVu is not available, fall back to Helvetica
    try:
        # Try system fonts first (installed via Dockerfile)
        system_font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Debian/Ubuntu
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',          # Some Linux distros
        ]
        
        font_found = False
        for font_path in system_font_paths:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
                font_name = 'DejaVuSans'
                font_found = True
                break
        
        # If system fonts not found, try our static directory
        if not font_found:
            static_font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                                    'static', 'fonts', 'DejaVuSans.ttf')
            if os.path.exists(static_font_path):
                pdfmetrics.registerFont(TTFont('DejaVuSans', static_font_path))
                font_name = 'DejaVuSans'
            else:
                raise FileNotFoundError(f"Font not found at {static_font_path}")
                
    except Exception as e:
        # Fall back to Helvetica (built-in) if no TTF fonts are available
        font_name = 'Helvetica'
    
    # If apartment is single, use its name; otherwise use "Apartments"
    apt_name = apartments[0].name if len(apartments) == 1 else "Apartments"
    
    x, y = 50, page_h - 250  # initial cursor
    
    # Set the font for the entire document
    pdf.setFont(font_name, 12)
    
    for apt in apartments:
        payload = f"apt_{apt.id}"
        url = _bot_link(payload)
        
        qr_img = qrcode.make(url, image_factory=PilImage)
        img_buf = io.BytesIO()
        qr_img.save(img_buf, format="PNG")
        img_buf.seek(0)
        
        pdf.drawImage(ImageReader(img_buf), x, y, width=200, height=200)
        
        # Use the registered font for text that might contain Cyrillic characters
        pdf.setFont(font_name, 12)
        label = f"Apartment #{apt.id}" + (f" – {apt.name}" if apt.name else "")
        pdf.drawString(x, y - 15, label)
        
        # advance cursor – 2 QR codes per row, 3 rows per page
        if x == 50:
            x = 300
        else:
            x = 50
            y -= 250
            if y < 100:
                pdf.showPage()
                y = page_h - 250
    
    pdf.save()
    buf.seek(0)
    
    # Properly handle filename encoding for Content-Disposition header
    # RFC 5987 encoding for non-ASCII characters in HTTP headers
    filename = apt_name + ".pdf"
    
    # For browsers that support RFC 5987
    filename_ascii = filename.encode('ascii', 'ignore').decode()
    filename_encoded = quote(filename.encode('utf-8'))
    
    if filename_ascii == filename:
        # ASCII-only filename, use simple format
        content_disposition = f'attachment; filename="{filename}"'
    else:
        # Non-ASCII filename, use both formats for compatibility
        content_disposition = f'attachment; filename="{filename_ascii}"; filename*=UTF-8\'\'{filename_encoded}'
    
    headers = {"Content-Disposition": content_disposition}
    return Response(content=buf.getvalue(), media_type="application/pdf", headers=headers)


@router.get("/dashboard", response_model=None)
async def get_dashboard(sess: SessionDep, user=Depends(current_user)):
    """Get landlord dashboard data."""
    user_id = await _get_landlord_id(sess, user)
    service = LandlordService(sess)
    
    try:
        data = await service.get_dashboard_data(user_id)
        return data
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) 