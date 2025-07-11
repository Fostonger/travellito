"""Landlord schemas for request/response models."""

from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field


# Apartment schemas
class ApartmentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    city_id: int = Field(..., gt=0)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)


class ApartmentOut(BaseModel):
    id: int
    name: str
    city_id: int
    city_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    model_config = {"from_attributes": True}


# Commission schemas
class CommissionBody(BaseModel):
    commission_pct: Decimal = Field(..., ge=0, le=100)

    model_config = {
        "json_schema_extra": {
            "example": {"commission_pct": "7.5"},
        },
    }


class CommissionOut(BaseModel):
    tour_id: int
    tour_title: str
    commission_pct: Decimal

    model_config = {"from_attributes": True}


# Tour with commission schema
class TourForLandlord(BaseModel):
    id: int
    title: str
    price: Decimal
    max_commission_pct: Decimal
    commission_pct: Decimal | None = None


# Earnings schema
class EarningsOut(BaseModel):
    total_tickets: int
    tickets_last_30d: int
    total_earnings: Decimal
    earnings_last_30d: Decimal 