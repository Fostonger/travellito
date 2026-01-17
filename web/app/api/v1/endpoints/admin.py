"""Admin endpoints for platform administration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status, UploadFile, File, Form, Response
from pydantic import ValidationError

from ....deps import SessionDep
from ....security import role_required
from ....services.admin_service import AdminService
from ....core.exceptions import NotFoundError, ConflictError
from ....storage import upload_qr_template, presigned
from ..schemas.admin_schemas import (
    MaxCommissionBody,
    MetricsOut,
    ApiKeyOut,
    ApiKeyCreate,
    UserOut,
    UserCreate,
    UserUpdate,
    QrTemplateOut,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(role_required("admin"))],
)


# Tour Commission Management
@router.patch("/tours/{tour_id}/max-commission", response_model=MaxCommissionBody)
async def set_max_commission(
    sess: SessionDep,
    tour_id: int = Path(..., gt=0),
    body: MaxCommissionBody | None = None,
):
    """Set maximum commission percentage for a tour."""
    if body is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    service = AdminService(sess)
    try:
        commission_pct = await service.set_tour_max_commission(tour_id, body.pct)
        return MaxCommissionBody(pct=commission_pct)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# Platform Metrics
@router.get("/metrics", response_model=MetricsOut)
async def metrics(sess: SessionDep):
    """Get platform-wide metrics."""
    service = AdminService(sess)
    metrics_data = await service.get_platform_metrics()
    return MetricsOut(**metrics_data)


# API Key Management
@router.post("/api-keys", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(payload: ApiKeyCreate, sess: SessionDep):
    """Create a new API key for an agency."""
    service = AdminService(sess)
    try:
        api_key = await service.create_api_key(payload.agency_id)
        return ApiKeyOut.model_validate(api_key)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(sess: SessionDep, limit: int = 100, offset: int = 0):
    """List all API keys."""
    service = AdminService(sess)
    api_keys = await service.list_api_keys(limit, offset)
    return [ApiKeyOut.model_validate(key) for key in api_keys]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(sess: SessionDep, key_id: int):
    """Delete an API key."""
    service = AdminService(sess)
    try:
        await service.delete_api_key(key_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# QR Template Management
@router.post("/qr-template", response_model=QrTemplateOut)
async def upload_qr_template_settings(
    sess: SessionDep,
    qr_template: UploadFile = File(None),
    qr_position_x: int = Form(..., gt=0),
    qr_position_y: int = Form(..., gt=0),
    qr_width: int = Form(..., gt=0),
    qr_height: int = Form(..., gt=0),
):
    """Upload and configure QR template image and positioning."""
    service = AdminService(sess)
    
    try:
        if qr_template:
            # Upload new template image to storage
            if qr_template.content_type not in ["image/png", "image/jpeg"]:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, 
                    detail="Only PNG and JPEG images are supported"
                )
            
            template_key = upload_qr_template(qr_template)
        else:
            # Get existing template key if available
            settings = await service.get_qr_template_settings()
            template_key = settings.get('template_url') if settings else None
        
        if not template_key:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="No template image provided and no existing template found"
            )
        
        # Save QR template settings
        settings = await service.save_qr_template_settings(
            template_url=template_key,
            position_x=qr_position_x,
            position_y=qr_position_y,
            width=qr_width,
            height=qr_height
        )
        
        # Generate URL for frontend preview
        settings["qr_template_url"] = presigned(settings["template_url"])
        
        return QrTemplateOut(**settings)
    
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/settings", response_model=dict)
async def get_settings(sess: SessionDep):
    """Get global settings including QR template settings."""
    service = AdminService(sess)
    settings = await service.get_global_settings()
    
    # Add QR template settings
    qr_settings = await service.get_qr_template_settings()
    if qr_settings and qr_settings.get("template_url"):
        settings["qr_template"] = True
        settings["qr_position_x"] = qr_settings.get("position_x", 50)
        settings["qr_position_y"] = qr_settings.get("position_y", 50)
        settings["qr_width"] = qr_settings.get("width", 200)
        settings["qr_height"] = qr_settings.get("height", 200)
        settings["qr_template_url"] = presigned(qr_settings["template_url"])
    
    return settings


@router.post("/settings", response_model=dict)
async def update_settings(sess: SessionDep, settings: dict):
    """Update global settings."""
    service = AdminService(sess)
    return await service.update_global_settings(settings)


# User Management
@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, sess: SessionDep):
    """Create a new user."""
    service = AdminService(sess)
    try:
        user = await service.create_user(
            email=payload.email,
            password=payload.password,
            role=payload.role,
            agency_id=payload.agency_id,
        )
        return UserOut.model_validate(user)
    except ConflictError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/users", response_model=list[UserOut])
async def list_users(sess: SessionDep, limit: int = 100, offset: int = 0):
    """List all users."""
    service = AdminService(sess)
    users = await service.list_users(limit, offset)
    return [UserOut.model_validate(user) for user in users]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, payload: UserUpdate, sess: SessionDep):
    """Update a user."""
    service = AdminService(sess)
    try:
        user = await service.update_user(
            user_id=user_id,
            email=payload.email,
            password=payload.password,
            role=payload.role,
            agency_id=payload.agency_id,
        )
        return UserOut.model_validate(user)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, sess: SessionDep):
    """Delete a user."""
    service = AdminService(sess)
    try:
        await service.delete_user(user_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) 


@router.get("/test-qr-pdf", response_class=Response)
async def test_qr_pdf(sess: SessionDep):
    """Generate a test PDF with the current QR template settings (4 A6 images on A4)."""
    try:
        from reportlab.pdfgen import canvas as _canvas
        from reportlab.lib.pagesizes import A4, A6
        from reportlab.lib.utils import ImageReader
        from PIL import Image as PILImage
        import io, tempfile, os

        # A6 dimensions in points
        A6_WIDTH_PT = A6[0]   # 297.64 points
        A6_HEIGHT_PT = A6[1]  # 419.53 points

        def _resize_to_a6(img: PILImage.Image, target_dpi: int = 300) -> PILImage.Image:
            """Resize and center-crop image to A6 format preserving quality."""
            a6_width_mm, a6_height_mm = 105, 148
            target_width = int(a6_width_mm * target_dpi / 25.4)
            target_height = int(a6_height_mm * target_dpi / 25.4)
            target_aspect = target_width / target_height
            orig_width, orig_height = img.size
            orig_aspect = orig_width / orig_height

            if orig_aspect > target_aspect:
                new_width = int(orig_height * target_aspect)
                left = (orig_width - new_width) // 2
                img = img.crop((left, 0, left + new_width, orig_height))
            elif orig_aspect < target_aspect:
                new_height = int(orig_width / target_aspect)
                top = (orig_height - new_height) // 2
                img = img.crop((0, top, orig_width, top + new_height))

            return img.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

        def _draw_cut_lines(pdf, page_width, page_height, a6_width, a6_height):
            """Draw thin cut lines between A6 images."""
            pdf.setStrokeColorRGB(0.7, 0.7, 0.7)
            pdf.setLineWidth(0.5)
            pdf.line(a6_width, 0, a6_width, page_height)
            pdf.line(0, a6_height, page_width, a6_height)

        # Get QR template settings
        service = AdminService(sess)
        qr_template_settings = await service.get_qr_template_settings()

        if not qr_template_settings or not qr_template_settings.get('template_url'):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="No QR template configured. Please upload a template image first."
            )

        # Get template settings
        template_url = qr_template_settings.get('template_url')
        orig_qr_pos_x = int(qr_template_settings.get('position_x', 50))
        orig_qr_pos_y = int(qr_template_settings.get('position_y', 50))
        orig_qr_width = int(qr_template_settings.get('width', 200))
        orig_qr_height = int(qr_template_settings.get('height', 200))

        from ....storage import client, BUCKET

        # Generate PDF
        buf = io.BytesIO()
        pdf = _canvas.Canvas(buf, pagesize=A4)
        page_w, page_h = A4

        try:
            # Get template image directly from S3, save to temp file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                client.fget_object(BUCKET, template_url, temp_file.name)
                template_path = temp_file.name

            # Load the image from the temp file at full quality
            template_pil = PILImage.open(template_path)
            orig_width, orig_height = template_pil.size

            if template_pil.mode != 'RGBA':
                template_pil = template_pil.convert('RGBA')

            # Resize to A6 format at 300 DPI with high quality
            template_a6 = _resize_to_a6(template_pil, target_dpi=300)
            a6_pixel_width, a6_pixel_height = template_a6.size

            # Calculate scale factor for QR position
            scale_x = a6_pixel_width / orig_width
            scale_y = a6_pixel_height / orig_height

            qr_pos_x_px = int(orig_qr_pos_x * scale_x)
            qr_pos_y_px = int(orig_qr_pos_y * scale_y)
            qr_width_px = int(orig_qr_width * scale_x)
            qr_height_px = int(orig_qr_height * scale_y)

            # Create a sample QR code image (black square with white border)
            qr_img = PILImage.new('RGBA', (400, 400), color='white')
            black_size = int(400 * 0.7)
            black_offset = (400 - black_size) // 2
            black_square = PILImage.new('RGBA', (black_size, black_size), color='black')
            qr_img.paste(black_square, (black_offset, black_offset))
            qr_img = qr_img.resize((qr_width_px, qr_height_px), PILImage.Resampling.LANCZOS)

            # Create composite image
            composite = template_a6.copy()
            composite.paste(qr_img, (qr_pos_x_px, qr_pos_y_px))

            # Clean up temp file
            os.unlink(template_path)

            # Grid positions for 4 A6 images on A4
            positions = [
                (0, A6_HEIGHT_PT),           # Top-left
                (A6_WIDTH_PT, A6_HEIGHT_PT), # Top-right
                (0, 0),                       # Bottom-left
                (A6_WIDTH_PT, 0),            # Bottom-right
            ]

            # Draw cut lines
            _draw_cut_lines(pdf, page_w, page_h, A6_WIDTH_PT, A6_HEIGHT_PT)

            # Place 4 test images on the page
            for x, y in positions:
                img_io = io.BytesIO()
                composite.save(img_io, format="PNG", optimize=False)
                img_io.seek(0)

                pdf.drawImage(
                    ImageReader(img_io),
                    x, y,
                    width=A6_WIDTH_PT,
                    height=A6_HEIGHT_PT,
                    preserveAspectRatio=False
                )

            # Add "TEST" watermark in center
            pdf.setFont("Helvetica-Bold", 48)
            pdf.setFillColorRGB(1, 0, 0, 0.3)  # Semi-transparent red
            pdf.drawCentredString(page_w / 2, page_h / 2, "TEST PDF")

        except Exception as e:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating test PDF: {str(e)}"
            )

        pdf.save()
        buf.seek(0)

        headers = {"Content-Disposition": "attachment; filename=qr_test.pdf"}
        return Response(content=buf.getvalue(), media_type="application/pdf", headers=headers)

    except ImportError:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF generation requires reportlab and Pillow packages"
        ) 