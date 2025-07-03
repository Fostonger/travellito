"""Admin endpoints for platform administration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import ValidationError

from ....deps import SessionDep
from ....security import role_required
from ....services.admin_service import AdminService
from ....core.exceptions import NotFoundError, ConflictError
from ..schemas.admin_schemas import (
    MaxCommissionBody,
    MetricsOut,
    ApiKeyOut,
    ApiKeyCreate,
    UserOut,
    UserCreate,
    UserUpdate,
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