from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


# Repetition schemas defined early to avoid forward refs
class RepetitionIn(BaseModel):
    repeat_type: str = Field(..., pattern="^(daily|weekly)$")
    repeat_weekdays: Optional[List[int]] = None
    repeat_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    timezone: Optional[str] = "UTC"

class RepetitionOut(BaseModel):
    id: int
    repeat_type: str
    repeat_weekdays: Optional[List[int]] = None
    repeat_time: str

    model_config = {
        "from_attributes": True,
    }


class TourIn(BaseModel):
    """Schema for creating tours"""
    title: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    city_id: Optional[int] = None
    category_ids: Optional[List[int]] = None  # Field for multiple categories
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    repeat_type: Optional[str] = Field(None, pattern="^(none|daily|weekly)$")
    repeat_weekdays: Optional[List[int]] = None  # 0=Mon .. 6=Sun
    repeat_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    timezone: Optional[str] = "UTC"  # Add timezone field with default UTC
    booking_template: Optional[str] = None  # Custom template for booking confirmations
    
    @field_validator('category_ids')
    def validate_category_ids(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError('Maximum 10 categories allowed')
        return v


class TourUpdate(BaseModel):
    """Schema for updating tours"""
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    city_id: Optional[int] = None
    category_ids: Optional[List[int]] = None  # Field for multiple categories
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    repeat_type: Optional[str] = Field(None, pattern="^(none|daily|weekly)$")
    repeat_weekdays: Optional[List[int]] = None  # 0=Mon .. 6=Sun
    repeat_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    timezone: Optional[str] = None  # Add timezone field
    booking_template: Optional[str] = None  # Custom template for booking confirmations
    
    @field_validator('category_ids')
    def validate_category_ids(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError('Maximum 10 categories allowed')
        return v


class TourOut(BaseModel):
    """Schema for tour responses"""
    id: int
    title: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    city_id: Optional[int] = None
    category_ids: Optional[List[int]] = None  # IDs of categories for this tour
    categories: Optional[List[str]] = None  # Category names for display
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    repeat_type: Optional[str] = None
    repeat_weekdays: Optional[List[int]] = None
    repeat_time: Optional[str] = None
    local_time: Optional[str] = None  # Add local time representation
    booking_template: Optional[str] = None  # Custom template for booking confirmations
    # multiple repetitions, optional
    repetitions: Optional[List[RepetitionOut]] = None

    model_config = {
        "from_attributes": True,
    }
    
    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        """Custom validation to handle time conversion"""
        if hasattr(obj, "__dict__"):
            # If it's an ORM object, handle time conversion
            data = {**obj.__dict__}
            # Remove category_id field as it's deprecated
            if "category_id" in data:
                del data["category_id"]
                
            if hasattr(obj, "repeat_time") and obj.repeat_time is not None:
                data["repeat_time"] = obj.repeat_time.strftime("%H:%M") if obj.repeat_time else None
                
            # Handle categories
            if hasattr(obj, "tour_categories"):
                data["category_ids"] = [cat.id for cat in obj.tour_categories]
                data["categories"] = [cat.name for cat in obj.tour_categories]
            
            # Handle repetitions if loaded
            reps_out = []
            if hasattr(obj, "repetitions") and obj.repetitions is not None:
                for r in obj.repetitions:
                    try:
                        time_str = r.repeat_time.strftime("%H:%M") if r.repeat_time else None
                    except Exception:
                        time_str = None
                    reps_out.append({
                        "id": r.id,
                        "repeat_type": r.repeat_type,
                        "repeat_weekdays": r.repeat_weekdays,
                        "repeat_time": time_str,
                    })
            if reps_out:
                data["repetitions"] = reps_out
                
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class ImagesOut(BaseModel):
    """Schema for image upload response"""
    keys: List[str]
    urls: List[str] 


class TicketCategoryIn(BaseModel):
    """Schema for creating/updating ticket categories"""
    ticket_class_id: int
    price: Decimal = Field(..., ge=0)


class TicketCategoryOut(BaseModel):
    """Schema for ticket category responses"""
    id: int
    tour_id: int
    ticket_class_id: int
    name: str
    price: Decimal

    model_config = {
        "from_attributes": True,
    } 