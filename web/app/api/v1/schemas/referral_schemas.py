"""Referral schemas for request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReferralIn(BaseModel):
    landlord_id: int = Field(..., gt=0, description="ID of the landlord owning the QR that was scanned")


class ScanIn(BaseModel):
    apartment_id: int = Field(..., gt=0, description="ID encoded in the QR code (apt_<id>_...)")


class ReferralResponse(BaseModel):
    ok: bool 