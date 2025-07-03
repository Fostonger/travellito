"""Referral endpoints for QR code scanning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ....deps import SessionDep
from ....security import role_required, current_user
from ....services.referral_service import ReferralService
from ....core.exceptions import NotFoundError
from ..schemas.referral_schemas import ReferralIn, ScanIn, ReferralResponse

router = APIRouter(
    prefix="/referrals",
    tags=["referrals"],
    dependencies=[Depends(role_required("bot_user"))]
)


@router.post("/", response_model=ReferralResponse, status_code=status.HTTP_201_CREATED)
async def record_referral(
    payload: ReferralIn, sess: SessionDep, user=Depends(current_user)
):
    """Register that the current user has scanned a landlord's QR.
    
    If a referral row for the same (user, landlord) already exists,
    just update its timestamp. Otherwise insert a new row.
    """
    service = ReferralService(sess)
    
    try:
        result = await service.record_landlord_referral(
            user_id=int(user["sub"]),
            landlord_id=payload.landlord_id
        )
        return ReferralResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/scan", response_model=ReferralResponse, status_code=status.HTTP_201_CREATED)
async def record_scan(
    payload: ScanIn, sess: SessionDep, user=Depends(current_user)
):
    """Variant of referral registration that receives apartment_id.
    
    Resolves landlord via the apartment and records the referral.
    """
    service = ReferralService(sess)
    
    try:
        result = await service.record_apartment_scan(
            user_id=int(user["sub"]),
            apartment_id=payload.apartment_id
        )
        return ReferralResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) 