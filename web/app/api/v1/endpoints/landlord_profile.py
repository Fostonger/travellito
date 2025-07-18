from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.deps import SessionDep
from app.security import current_user, role_required, _extract_token, decode_token
from app.services.landlord_profile_service import LandlordProfileService
from app.services.landlord_service import LandlordService
from app.core.unit_of_work import UnitOfWork

# Create router with landlord role requirement for all routes
router = APIRouter(
    tags=["landlord-profile"],
    dependencies=[Depends(role_required("landlord"))],
)

# Templates setup
templates = Jinja2Templates(directory="templates")


class PaymentInfoUpdate(BaseModel):
    """Schema for updating payment information"""
    phone_number: Optional[str] = None
    bank_name: Optional[str] = None


async def _get_landlord_id(sess: SessionDep, user: dict) -> int:
    """Extract landlord ID from user token."""
    try:
        user_id = int(user["sub"])
        service = LandlordService(sess)
        landlord = await service.get_landlord_by_user_id(user_id)
        return landlord.id
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid landlord token")


@router.get("/profile", response_class=HTMLResponse)
async def get_profile_page(
    request: Request,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Render profile page with payment information"""
    try:
        # Get user_id from token sub claim
        landlord_id = await _get_landlord_id(sess, user)
        service = LandlordService(sess)
        landlord = await service.get_landlord_by_user_id(int(user["sub"]))
        
        if not landlord:
            raise HTTPException(status_code=404, detail="Landlord profile not found")
        
        return templates.TemplateResponse(
            "partner/profile.html",
            {
                "request": request,
                "user": user,
                "landlord": landlord,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving profile: {str(e)}")


@router.post("/profile/payment")
async def update_payment_info(
    payment_info: PaymentInfoUpdate,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Update landlord payment information"""
    try:
        # Get user_id from token sub claim
        landlord_id = await _get_landlord_id(sess, user)
        
        # Get service
        uow = UnitOfWork(sess)
        service = LandlordProfileService(uow)
        
        success = await service.update_payment_info(
            landlord_id=landlord_id,
            phone_number=payment_info.phone_number,
            bank_name=payment_info.bank_name,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update payment information")
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")


@router.post("/logout")
async def logout(response: Response):
    """Log out the user"""
    # Delete session cookie
    response.delete_cookie(key="session")
    return {"success": True, "message": "Token invalidated"}


@router.get("/debug-token", response_class=JSONResponse)
async def debug_token(request: Request):
    """Debug endpoint to check token extraction"""
    try:
        # Extract token directly
        token = await _extract_token(request)
        if not token:
            return {"error": "No token found in request"}
            
        # Try to decode the token
        decoded = decode_token(token)
        
        # Return token info
        return {
            "token_found": True,
            "token_prefix": token[:10] + "..." if token else None,
            "decoded": decoded,
            "auth_header": request.headers.get("Authorization"),
            "cookies": dict(request.cookies)
        }
    except Exception as e:
        return {
            "error": str(e),
            "auth_header": request.headers.get("Authorization"),
            "cookies": dict(request.cookies)
        } 