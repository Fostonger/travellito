from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

from ....deps import SessionDep
from app.security import current_user
from ....services import SupportService
from ..schemas.support_schemas import (
    SupportMessageCreate, SupportMessageOut, SupportResponseCreate,
    PaymentRequestOut, PaymentProcessRequest
)
from ....core.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/messages", response_model=SupportMessageOut)
async def create_support_message(
    sess: SessionDep,
    data: SupportMessageCreate,
    user=Depends(current_user)
):
    """Create a new support message (question/issue)."""
    service = SupportService(sess)
    
    try:
        message = await service.create_support_message(
            user_id=user["sub"],
            message_type=data.message_type,
            message=data.message
        )
        
        # Manually construct the response to avoid lazy loading
        # Get the user object explicitly
        from sqlalchemy import select
        from ....models import User
        
        user_stmt = select(User).where(User.id == message.user_id)
        user_obj = await sess.scalar(user_stmt)
        
        # Construct response without accessing relationships directly
        return SupportMessageOut(
            id=message.id,
            user_id=message.user_id,
            message_type=message.message_type,
            message=message.message,
            created_at=message.created_at,
            status=message.status,
            user={
                "id": user_obj.id,
                "first": user_obj.first,
                "last": user_obj.last,
                "username": user_obj.username
            },
            responses=[]  # Initially empty for new messages
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/messages", response_model=List[SupportMessageOut])
async def list_support_messages(
    sess: SessionDep,
    status: Optional[str] = None,
    message_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user=Depends(current_user)
):
    """List support messages. Admin only."""
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    service = SupportService(sess)
    
    # Use the modified method that uses eager loading
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from ....models import SupportMessage, User, SupportResponse
    
    # Build the query with proper eager loading
    stmt = select(SupportMessage).options(
        selectinload(SupportMessage.user),
        selectinload(SupportMessage.responses).selectinload(SupportResponse.admin)
    )
    
    if status:
        stmt = stmt.where(SupportMessage.status == status)
    if message_type:
        stmt = stmt.where(SupportMessage.message_type == message_type)
        
    stmt = stmt.order_by(SupportMessage.created_at.desc()).limit(limit).offset(offset)
    
    result = await sess.execute(stmt)
    messages = result.scalars().all()
    
    # Manually transform to avoid lazy loading issues
    response_messages = []
    for msg in messages:
        # Construct user info
        user_info = {
            "id": msg.user.id,
            "first": msg.user.first,
            "last": msg.user.last,
            "username": msg.user.username
        } if msg.user else None
        
        # Construct admin info if assigned
        admin_info = None
        if msg.assigned_admin:
            admin_info = {
                "id": msg.assigned_admin.id,
                "first": msg.assigned_admin.first, 
                "last": msg.assigned_admin.last,
                "username": msg.assigned_admin.username
            }
        
        # Construct response objects
        responses = []
        for resp in msg.responses:
            admin = {
                "id": resp.admin.id,
                "first": resp.admin.first,
                "last": resp.admin.last,
                "username": resp.admin.username
            } if resp.admin else None
            
            responses.append({
                "id": resp.id,
                "response": resp.response,
                "created_at": resp.created_at,
                "admin": admin
            })
        
        # Create the message object
        response_messages.append(SupportMessageOut(
            id=msg.id,
            user_id=msg.user_id,
            message_type=msg.message_type,
            message=msg.message,
            created_at=msg.created_at,
            status=msg.status,
            user=user_info,
            assigned_admin=admin_info,
            responses=responses
        ))
    
    return response_messages


@router.get("/messages/{message_id}", response_model=SupportMessageOut)
async def get_support_message(
    sess: SessionDep,
    message_id: int,
    user=Depends(current_user)
):
    """Get a specific support message. Admin or message owner only."""
    # Use direct query with eager loading 
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from ....models import SupportMessage, SupportResponse
    
    stmt = (
        select(SupportMessage)
        .where(SupportMessage.id == message_id)
        .options(
            selectinload(SupportMessage.user),
            selectinload(SupportMessage.assigned_admin),
            selectinload(SupportMessage.responses).selectinload(SupportResponse.admin)
        )
    )
    result = await sess.execute(stmt)
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")
    
    # Check access
    if user["role"] != "admin" and message.user_id != int(user["sub"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    # Manually construct response to avoid lazy loading issues
    user_info = {
        "id": message.user.id,
        "first": message.user.first,
        "last": message.user.last,
        "username": message.user.username
    } if message.user else None
    
    admin_info = None
    if message.assigned_admin:
        admin_info = {
            "id": message.assigned_admin.id,
            "first": message.assigned_admin.first,
            "last": message.assigned_admin.last,
            "username": message.assigned_admin.username
        }
    
    responses = []
    for resp in message.responses:
        admin = {
            "id": resp.admin.id,
            "first": resp.admin.first,
            "last": resp.admin.last,
            "username": resp.admin.username
        } if resp.admin else None
        
        responses.append({
            "id": resp.id,
            "response": resp.response,
            "created_at": resp.created_at,
            "admin": admin
        })
    
    return SupportMessageOut(
        id=message.id,
        user_id=message.user_id,
        message_type=message.message_type,
        message=message.message,
        created_at=message.created_at,
        status=message.status,
        user=user_info,
        assigned_admin=admin_info,
        responses=responses
    )


@router.post("/messages/{message_id}/respond")
async def respond_to_message(
    sess: SessionDep,
    message_id: int,
    data: SupportResponseCreate,
    user=Depends(current_user)
):
    """Respond to a support message. Admin only."""
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    service = SupportService(sess)
    
    try:
        # Convert user["sub"] to integer
        admin_id = int(user["sub"])
        
        response = await service.respond_to_support_message(
            message_id=message_id,
            admin_id=admin_id,  # Now properly converted to int
            response_text=data.response,
            mark_resolved=data.mark_resolved
        )
        return {"status": "success", "response_id": response.id}
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid admin ID format")
    except NotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Message not found")


# Internal endpoint for getting admin telegram IDs
@router.get("/internal/admin-telegram-ids")
async def get_admin_telegram_ids(sess: SessionDep):
    """Internal endpoint to get admin users with telegram IDs."""
    from sqlalchemy import select, and_
    from ....models import User
    
    stmt = select(User.tg_id).where(
        and_(
            User.role == "admin",
            User.tg_id.isnot(None)
        )
    )
    result = await sess.execute(stmt)
    admin_ids = [row[0] for row in result]
    
    return admin_ids


# Payment request endpoints for landlords

@router.post("/payment-requests/{request_id}/process")
async def process_payment_request(
    sess: SessionDep,
    request_id: int,
    data: PaymentProcessRequest,
    user=Depends(current_user)
):
    """Process a payment request. Admin only."""
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    service = SupportService(sess)
    
    try:
        # Convert user["sub"] to integer
        admin_id = int(user["sub"])
        
        request = await service.process_payment_request(
            request_id=request_id,
            admin_id=admin_id,  # Now properly converted to int
            status=data.status
        )
        return {"status": "success", "payment_request": PaymentRequestOut.model_validate(request)}
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid admin ID format")
    except NotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payment request not found")
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) 