"""Admin schemas for request/response models."""

from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field


# Commission schemas
class MaxCommissionBody(BaseModel):
    pct: Decimal = Field(..., ge=0, le=100)


# Metrics schema
class MetricsOut(BaseModel):
    agencies: int
    landlords: int
    tours: int
    departures: int
    bookings: int
    tickets_sold: int
    sales_amount: Decimal


# API Key schemas
class ApiKeyOut(BaseModel):
    id: int
    agency_id: int
    key: str

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    agency_id: int = Field(..., gt=0)


# User schemas
class UserOut(BaseModel):
    id: int
    email: str | None = None
    role: str
    first: str | None = None
    last: str | None = None
    tg_id: int | None = None
    agency_id: int | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = Field(..., pattern="^(admin|agency|landlord|manager)$")
    agency_id: int | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    role: str | None = Field(None, pattern="^(admin|agency|landlord|manager)$")
    agency_id: int | None = None 