from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DepartureIn(BaseModel):
    """Schema for creating departures"""
    tour_id: int = Field(..., gt=0)
    starts_at: datetime
    capacity: int = Field(..., gt=0)


class DepartureUpdate(BaseModel):
    """Schema for updating departures"""
    starts_at: Optional[datetime] = None
    capacity: Optional[int] = Field(None, gt=0)


class DepartureOut(BaseModel):
    """Schema for departure responses"""
    id: int
    tour_id: int
    starts_at: datetime
    capacity: int
    modifiable: bool

    model_config = {
        "from_attributes": True,
    }


class CapacityUpdate(BaseModel):
    """Schema for updating only capacity"""
    capacity: int = Field(..., gt=0) 