"""Manager endpoints for agency manager operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ....deps import SessionDep
from ....security import current_user, role_required
from ....services.manager_service import ManagerService
from ....core.exceptions import NotFoundError, ConflictError
from ..schemas.manager_schemas import ManagerIn, ManagerOut
from .utils import get_agency_id

router = APIRouter(
    prefix="/managers",
    tags=["managers"],
    dependencies=[Depends(role_required("agency"))],
)


@router.get("", response_model=list[ManagerOut])
async def list_managers(sess: SessionDep, user=Depends(current_user)):
    """List all managers for the agency."""
    agency_id = get_agency_id(user)
    service = ManagerService(sess)
    managers = await service.list_managers(agency_id)
    return [ManagerOut.model_validate(mgr) for mgr in managers]


@router.post("", response_model=ManagerOut, status_code=status.HTTP_201_CREATED)
async def create_manager(payload: ManagerIn, sess: SessionDep, user=Depends(current_user)):
    """Create a new manager for the agency."""
    agency_id = get_agency_id(user)
    service = ManagerService(sess)
    
    try:
        manager = await service.create_manager(
            agency_id=agency_id,
            email=payload.email,
            password=payload.password,
            first=payload.first,
            last=payload.last,
        )
        return ManagerOut.model_validate(manager)
    except ConflictError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{mgr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manager(mgr_id: int, sess: SessionDep, user=Depends(current_user)):
    """Delete a manager from the agency."""
    agency_id = get_agency_id(user)
    service = ManagerService(sess)
    
    try:
        await service.delete_manager(agency_id, mgr_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) 