"""Broadcast endpoints for messaging operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Path, status, BackgroundTasks

from ....deps import SessionDep
from ....models import User
from ....security import role_required, current_user
from ....services.broadcast_service import BroadcastService
from ....core.exceptions import NotFoundError, AuthorizationError
from ..schemas.broadcast_schemas import BroadcastBody, BroadcastResponse, DepartureOut

router = APIRouter(prefix="/departures", tags=["broadcast"])


async def _do_broadcast_task(
    broadcast_service: BroadcastService,
    departure_id: int,
    message: BroadcastBody
):
    """Background task to send broadcast messages."""
    chat_ids = await broadcast_service.get_chat_ids_for_departure(departure_id)
    await broadcast_service.send_broadcast(
        chat_ids=chat_ids,
        text=message.text,
        photo_url=message.photo_url,
        document_url=message.document_url,
    )


@router.post(
    "/{departure_id}/broadcast",
    response_model=BroadcastResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(role_required(["bot", "manager"]))]
)
async def broadcast(
    background_tasks: BackgroundTasks,
    sess: SessionDep,
    departure_id: int = Path(..., gt=0),
    payload: BroadcastBody | None = None,
    user=Depends(current_user),
):
    """Asynchronously broadcast to tourists booked on the departure."""
    if payload is None or not any([payload.text, payload.photo_url, payload.document_url]):
        raise HTTPException(400, "Payload cannot be empty")
    
    service = BroadcastService(sess)
    
    try:
        # Validate permissions
        await service.validate_broadcast_permission(
            departure_id=departure_id,
            user_id=int(user["sub"]),
            user_role=user["role"]
        )
        
        # Schedule background send
        background_tasks.add_task(
            _do_broadcast_task,
            service,
            departure_id,
            payload
        )
        
        return BroadcastResponse(scheduled=True)
        
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthorizationError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get(
    "/",
    response_model=list[DepartureOut],
    dependencies=[Depends(role_required(["admin", "bot", "manager"]))]
)
async def list_departures(sess: SessionDep, user=Depends(current_user)):
    """Return upcoming departures with at least one booking.
    
    - Admin/bot roles: all departures
    - Manager: only departures belonging to their agency
    """
    service = BroadcastService(sess)
    
    # Get agency_id for managers
    agency_id = None
    if user["role"] == "manager":
        mgr: User | None = await sess.get(User, int(user["sub"]))
        if not mgr or mgr.agency_id is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Manager not linked to any agency"
            )
        agency_id = mgr.agency_id
    
    departures = await service.list_departures_for_broadcast(
        user_role=user["role"],
        agency_id=agency_id
    )
    
    return [DepartureOut(**dep) for dep in departures] 