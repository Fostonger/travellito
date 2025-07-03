"""External API schemas for request/response models."""

from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field


# Capacity schemas
class CapacityBody(BaseModel):
    capacity: int = Field(..., gt=0)


class CapacityOut(BaseModel):
    id: int
    capacity: int


# Booking export schemas
class BookingExportItem(BaseModel):
    booking_id: int
    departure_id: int
    starts_at: str | None
    tour_title: str
    qty: int
    net_price: str 