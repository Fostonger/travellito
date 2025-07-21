"""Admin endpoints for platform administration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status, UploadFile, File, Form
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