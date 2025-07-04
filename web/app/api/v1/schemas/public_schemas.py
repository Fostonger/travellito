"""Public schemas for request/response models."""

from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


# Tour schemas
class TourSearchOut(BaseModel):
    id: int
    title: str
    price_raw: str
    price_net: str
    category: str | None


class TourListOut(BaseModel):
    id: int
    title: str
    price: str


class TourDetailOut(BaseModel):
    id: int
    title: str
    description: str | None
    price: str
    duration_minutes: int | None
    images: List[dict]


# Category schemas
class CategoryOut(BaseModel):
    id: int
    name: str
    price_raw: str
    price_net: str


# Quote schemas
class QuoteItem(BaseModel):
    category_id: int
    qty: int = Field(gt=0)


class QuoteIn(BaseModel):
    departure_id: int
    items: List[QuoteItem]
    virtual_timestamp: Optional[int] = None  # Timestamp in milliseconds for virtual departures


class QuoteOut(BaseModel):
    total_net: Decimal
    seats_left: int
    departure_id: int | None = None


# Departure schemas
class DepartureListOut(BaseModel):
    id: int | None
    starts_at: str
    capacity: int
    seats_left: int
    is_virtual: bool


class DepartureAvailabilityOut(BaseModel):
    departure_id: int
    capacity: int
    seats_taken: int
    seats_left: int


# List schemas
class CityOut(BaseModel):
    id: int
    name: str


class TourCategoryOut(BaseModel):
    id: int
    name: str


class TicketClassOut(BaseModel):
    id: int
    code: str
    name: str


class RepetitionTypeOut(BaseModel):
    """Schema for repetition type output."""
    id: int
    name: str


class LandlordSignupRequest(BaseModel):
    """Schema for landlord signup request."""
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6) 