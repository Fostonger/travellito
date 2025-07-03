from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field


class TourIn(BaseModel):
    """Schema for creating/updating tours"""
    title: str
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0)
    duration_minutes: Optional[int] = Field(None, gt=0)
    city_id: Optional[int] = None
    category_id: Optional[int] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    repeat_type: Optional[str] = Field(None, pattern="^(none|daily|weekly)$")
    repeat_weekdays: Optional[List[int]] = None  # 0=Mon .. 6=Sun
    repeat_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")


class TourOut(BaseModel):
    """Schema for tour responses"""
    id: int
    title: str
    description: Optional[str] = None
    price: Decimal
    duration_minutes: Optional[int] = None
    city_id: Optional[int] = None
    category_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    repeat_type: Optional[str] = None
    repeat_weekdays: Optional[List[int]] = None
    repeat_time: Optional[str] = None

    model_config = {
        "from_attributes": True,
    }
    
    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        """Custom validation to handle time conversion"""
        if hasattr(obj, "__dict__"):
            # If it's an ORM object, handle time conversion
            data = {**obj.__dict__}
            if hasattr(obj, "repeat_time") and obj.repeat_time is not None:
                data["repeat_time"] = obj.repeat_time.strftime("%H:%M") if obj.repeat_time else None
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class ImagesOut(BaseModel):
    """Schema for image upload response"""
    keys: List[str]
    urls: List[str] 