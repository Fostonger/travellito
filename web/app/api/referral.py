from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..models import Referral, Landlord, Apartment
from ..deps import SessionDep
from ..security import role_required, current_user

router = APIRouter(prefix="/referrals", tags=["referrals"],
                   dependencies=[Depends(role_required("bot_user"))])


class ReferralIn(BaseModel):
    landlord_id: int = Field(..., gt=0, description="ID of the landlord owning the QR that was scanned")


class ScanIn(BaseModel):
    apartment_id: int = Field(..., gt=0, description="ID encoded in the QR code (apt_<id>_...)")


@router.post("/", status_code=status.HTTP_201_CREATED)
async def record_referral(payload: ReferralIn, sess: SessionDep, user=Depends(current_user)):
    """Register that the *current user* has just scanned a landlord's QR.

    – If a Referral row for the same (user, landlord) already exists, just update its *ts*.
    – Otherwise insert a new row.  The *last scanned* landlord is the one with latest ts.
    """
    # Validate landlord exists (defence-in-depth)
    landlord: Landlord | None = await sess.get(Landlord, payload.landlord_id)
    if not landlord:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Landlord not found")

    stmt = select(Referral).where(
        Referral.user_id == int(user["sub"]),
        Referral.landlord_id == payload.landlord_id,
    )
    ref: Referral | None = await sess.scalar(stmt)

    if ref is None:
        ref = Referral(user_id=int(user["sub"]), landlord_id=payload.landlord_id, ts=datetime.utcnow())
        sess.add(ref)
    else:
        ref.ts = datetime.utcnow()

    await sess.commit()
    return {"ok": True}


@router.post("/scan", status_code=status.HTTP_201_CREATED)
async def record_scan(payload: ScanIn, sess: SessionDep, user=Depends(current_user)):
    """Variant of referral registration that receives *apartment_id*.

    – Resolves landlord via the Apartment row and forwards to the same logic as
      `/referrals`.
    """
    apt: Apartment | None = await sess.get(Apartment, payload.apartment_id)
    if not apt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Apartment not found")

    # Reuse existing referral logic by delegating landlord_id
    return await record_referral(ReferralIn(landlord_id=apt.landlord_id), sess, user) 