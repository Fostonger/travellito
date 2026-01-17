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
    from reportlab.lib.pagesizes import A4, A6
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.units import mm
    from PIL import Image as PILImage
    HAS_QR_SUPPORT = True
except ImportError:
    HAS_QR_SUPPORT = False

# A6 dimensions in points (for PDF generation)
A6_WIDTH_PT = A6[0] if HAS_QR_SUPPORT else 297.64   # 105mm = 297.64 points
A6_HEIGHT_PT = A6[1] if HAS_QR_SUPPORT else 419.53  # 148mm = 419.53 points

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
    """Return link to our redirect endpoint that will then forward to Telegram bot."""
    # Extract apartment ID from payload (format: "apt_123")
    apt_id = payload.split('_')[1] if payload.startswith('apt_') else payload
    # Get server host from environment variable or use default
    server_host = os.getenv("SERVER_HOST", "http://localhost:8000")
    # Create absolute URL to our redirect endpoint
    return f"{server_host}/api/v1/public/redirect/apartment/{apt_id}"


def _resize_to_a6(img: "PILImage.Image", target_dpi: int = 300) -> "PILImage.Image":
    """
    Resize and center-crop image to A6 format (105mm x 148mm) preserving quality.
    Uses high-quality LANCZOS resampling to avoid blurriness.

    Args:
        img: PIL Image to resize
        target_dpi: Target DPI for the output image (default 300 for print quality)

    Returns:
        PIL Image resized to A6 dimensions at specified DPI
    """
    # A6 dimensions in mm: 105 x 148
    a6_width_mm = 105
    a6_height_mm = 148

    # Calculate target pixel dimensions at specified DPI
    target_width = int(a6_width_mm * target_dpi / 25.4)   # ~1240 pixels at 300 DPI
    target_height = int(a6_height_mm * target_dpi / 25.4)  # ~1748 pixels at 300 DPI

    # A6 aspect ratio
    target_aspect = target_width / target_height

    # Original image dimensions
    orig_width, orig_height = img.size
    orig_aspect = orig_width / orig_height

    # Determine how to crop/scale to match A6 aspect ratio (center crop)
    if orig_aspect > target_aspect:
        # Image is wider than A6 - crop sides
        new_width = int(orig_height * target_aspect)
        left = (orig_width - new_width) // 2
        img = img.crop((left, 0, left + new_width, orig_height))
    elif orig_aspect < target_aspect:
        # Image is taller than A6 - crop top/bottom
        new_height = int(orig_width / target_aspect)
        top = (orig_height - new_height) // 2
        img = img.crop((0, top, orig_width, top + new_height))

    # Resize to target dimensions using high-quality LANCZOS resampling
    img = img.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

    return img


def _draw_cut_lines(pdf, page_width: float, page_height: float, a6_width: float, a6_height: float):
    """
    Draw thin cut lines between A6 images on the A4 page.

    Args:
        pdf: ReportLab canvas
        page_width: A4 page width in points
        page_height: A4 page height in points
        a6_width: A6 width in points
        a6_height: A6 height in points
    """
    pdf.setStrokeColorRGB(0.7, 0.7, 0.7)  # Light gray
    pdf.setLineWidth(0.5)  # Thin line

    # Vertical cut line (center)
    pdf.line(a6_width, 0, a6_width, page_height)

    # Horizontal cut line (center)
    pdf.line(0, a6_height, page_width, a6_height)


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
    
    # Get QR template settings
    qr_template_settings = await service.get_qr_template_settings()
    qr_template_url = qr_template_settings.get('template_url') if qr_template_settings else None
    
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
    
    # Generate PDF with template if available
    if qr_template_settings and qr_template_url:
        # Template-based QR codes - 4 A6 images per A4 page
        try:
            from ....storage import presigned, client, BUCKET
            import tempfile

            # Get template settings for QR placement (in original image pixels)
            orig_qr_pos_x = int(qr_template_settings.get('position_x', 50))
            orig_qr_pos_y = int(qr_template_settings.get('position_y', 50))
            orig_qr_width = int(qr_template_settings.get('width', 200))
            orig_qr_height = int(qr_template_settings.get('height', 200))

            # Get template image directly from S3, save to a temp file first
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                client.fget_object(BUCKET, qr_template_url, temp_file.name)
                template_path = temp_file.name

            # Load the image from the temp file at full quality
            template_pil = PILImage.open(template_path)
            orig_width, orig_height = template_pil.size

            # Convert to RGBA if not already (for transparency support)
            if template_pil.mode != 'RGBA':
                template_pil = template_pil.convert('RGBA')

            # Resize template to A6 format at 300 DPI while preserving quality
            # This handles center-cropping if aspect ratio doesn't match A6
            template_a6 = _resize_to_a6(template_pil, target_dpi=300)
            a6_pixel_width, a6_pixel_height = template_a6.size

            # Calculate scale factor for QR position (from original to A6)
            scale_x = a6_pixel_width / orig_width
            scale_y = a6_pixel_height / orig_height

            # Calculate proportional QR position and size in A6 pixels
            qr_pos_x_px = int(orig_qr_pos_x * scale_x)
            qr_pos_y_px = int(orig_qr_pos_y * scale_y)
            qr_width_px = int(orig_qr_width * scale_x)
            qr_height_px = int(orig_qr_height * scale_y)

            # Pre-generate composite images for each apartment
            composite_images = []
            for apt in apartments:
                payload = f"apt_{apt.id}"
                url = _bot_link(payload)

                # Create high-resolution QR code
                qr = qrcode.QRCode(
                    version=None,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=2,
                )
                qr.add_data(url)
                qr.make(fit=True)
                qr_img = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")

                # Resize QR code to target size with high quality
                qr_img = qr_img.resize((qr_width_px, qr_height_px), PILImage.Resampling.LANCZOS)

                # Create composite: paste QR onto template copy
                composite = template_a6.copy()
                # Convert QR to RGBA for proper pasting
                if qr_img.mode != 'RGBA':
                    qr_img = qr_img.convert('RGBA')
                composite.paste(qr_img, (qr_pos_x_px, qr_pos_y_px))

                composite_images.append(composite)

            # Clean up temp file
            os.unlink(template_path)

            # Layout: 4 A6 images per A4 page (2 columns x 2 rows)
            # A4 in points: 595.28 x 841.89
            # A6 in points: 297.64 x 419.53
            # So 2 A6 fit horizontally (297.64 * 2 = 595.28)
            # And 2 A6 fit vertically (419.53 * 2 = 839.06, slightly less than 841.89)

            page_w, page_h = A4
            a6_w_pt = A6_WIDTH_PT
            a6_h_pt = A6_HEIGHT_PT

            # Grid positions for 4 A6 images on A4 (bottom-left origin)
            # Row 1 (top): y = a6_h_pt, Row 0 (bottom): y = 0
            # Col 0 (left): x = 0, Col 1 (right): x = a6_w_pt
            positions = [
                (0, a6_h_pt),           # Top-left
                (a6_w_pt, a6_h_pt),     # Top-right
                (0, 0),                  # Bottom-left
                (a6_w_pt, 0),           # Bottom-right
            ]

            idx = 0
            while idx < len(composite_images):
                # Draw cut lines first (so they appear behind images if needed)
                _draw_cut_lines(pdf, page_w, page_h, a6_w_pt, a6_h_pt)

                # Place up to 4 images on this page
                for pos_idx, (x, y) in enumerate(positions):
                    if idx >= len(composite_images):
                        break

                    # Convert composite image to bytes for ReportLab
                    img_io = io.BytesIO()
                    composite_images[idx].save(img_io, format="PNG", optimize=False)
                    img_io.seek(0)

                    # Draw image at position with exact A6 dimensions
                    pdf.drawImage(
                        ImageReader(img_io),
                        x, y,
                        width=a6_w_pt,
                        height=a6_h_pt,
                        preserveAspectRatio=False
                    )

                    idx += 1

                # Start new page if more images remain
                if idx < len(composite_images):
                    pdf.showPage()

        except Exception as e:
            # Fall back to standard QR code generation if template fails
            print(f"Error using QR template: {str(e)}")
            import traceback
            traceback.print_exc()
            _generate_standard_qr_pdf(pdf, apartments, font_name)
            # Clean up temporary file if it exists
            if 'template_path' in locals():
                try:
                    os.unlink(template_path)
                except Exception:
                    pass
    else:
        # Standard QR code generation
        _generate_standard_qr_pdf(pdf, apartments, font_name)
    
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


# Helper function for standard QR generation
def _generate_standard_qr_pdf(pdf, apartments, font_name):
    """Generate standard QR codes without template"""
    x, y = 50, A4[1] - 250  # initial cursor
    
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
        label = f"Apartment" + (f" – {apt.name}" if apt.name else "")
        pdf.drawString(x, y - 15, label)
        
        # advance cursor – 2 QR codes per row, 3 rows per page
        if x == 50:
            x = 300
        else:
            x = 50
            y -= 250
            if y < 100:
                pdf.showPage()
                y = A4[1] - 250


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


# Payment request endpoints

@router.get("/payment/status")
async def get_payment_status(sess: SessionDep, user=Depends(current_user)):
    """Get payment request eligibility and balance info."""
    from ....services import SupportService
    
    landlord_id = await _get_landlord_id(sess, user)
    support_service = SupportService(sess)
    
    try:
        # Get eligibility info
        eligibility = await support_service.can_request_payment(landlord_id)
        
        # Get balance info
        balance_info = await support_service.get_landlord_balance_info(landlord_id)
        
        return {
            "can_request": eligibility["can_request"],
            "reason": eligibility["reason"],
            "available_amount": str(eligibility["available_amount"]),
            "unique_users_count": eligibility["unique_users_count"],
            "has_payment_info": eligibility["has_payment_info"],
            "total_earned": str(balance_info["total_earned"]),
            "total_paid": str(balance_info["total_paid"]),
            "available_balance": str(balance_info["available_balance"]),
            "pending_request": balance_info["pending_request"] is not None,
            "pending_request_amount": str(balance_info["pending_request"].amount) if balance_info["pending_request"] else None
        }
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/payment/request")
async def request_payment(sess: SessionDep, user=Depends(current_user)):
    """Request a payment for available commissions."""
    from ....services import SupportService
    
    landlord_id = await _get_landlord_id(sess, user)
    support_service = SupportService(sess)
    
    try:
        payment_request = await support_service.create_payment_request(landlord_id)
        
        return {
            "status": "success",
            "message": "Запрос на выплату успешно создан",
            "request_id": payment_request.id,
            "amount": str(payment_request.amount)
        }
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) 