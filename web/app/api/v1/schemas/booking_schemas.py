from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field


class BookingStatusUpdate(BaseModel):
    """Schema for updating booking status"""
    status: str = Field(..., pattern="^(confirmed|rejected)$")


class CategoryBreakdown(BaseModel):
    """Schema for category breakdown in bookings"""
    name: str
    quantity: int
    amount: Decimal


class BookingOut(BaseModel):
    """Schema for booking responses"""
    id: int
    booking_date: datetime
    tour_title: str
    departure_date: datetime
    customer_name: str
    customer_phone: Optional[str]
    total_quantity: int
    total_amount: Decimal
    commission_percent: Decimal
    commission_amount: Decimal
    status: str
    viewed: bool
    categories: List[CategoryBreakdown]

    model_config = {
        "from_attributes": True,
    }


class BookingExportOut(BaseModel):
    """Schema for booking export data"""
    booking_id: int
    booking_date: str  # ISO format string
    tour_title: str
    departure_date: str  # ISO format string
    customer_name: str
    customer_phone: str
    total_quantity: int
    total_amount: float
    commission_percent: float
    commission_amount: float
    status: str
    viewed: bool
    categories: List[Dict[str, Any]]


class BookingMetrics(BaseModel):
    """Schema for booking metrics"""
    total: int
    pending: int
    confirmed: int
    rejected: int 


class TouristBookingOut(BaseModel):
    """Schema for tourist bookings with tour and departure details"""
    id: int
    amount: float
    status: str
    created: datetime
    departure_date: datetime
    tour_title: str
    tour_id: int
    departure_id: int
    is_cancellable: bool = False
    items: List[Dict[str, Any]] = [] 
    tour_address: Optional[str] = None 