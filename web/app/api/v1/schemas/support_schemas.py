from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class SupportMessageCreate(BaseModel):
    message_type: str = Field(..., pattern="^(issue|question)$")
    message: str = Field(..., min_length=1, max_length=2000)


class SupportResponseCreate(BaseModel):
    response: str = Field(..., min_length=1, max_length=2000)
    mark_resolved: bool = False


class UserInfo(BaseModel):
    id: int
    first: Optional[str] = None
    last: Optional[str] = None
    username: Optional[str] = None
    
    model_config = {"from_attributes": True}


class SupportResponseOut(BaseModel):
    id: int
    response: str
    created_at: datetime
    admin: UserInfo
    
    model_config = {"from_attributes": True}


class SupportMessageOut(BaseModel):
    id: int
    user_id: int
    message_type: str
    message: str
    created_at: datetime
    status: str
    user: UserInfo
    assigned_admin: Optional[UserInfo] = None
    responses: List[SupportResponseOut] = []
    
    model_config = {"from_attributes": True}


class PaymentRequestOut(BaseModel):
    id: int
    landlord_id: int
    amount: Decimal
    phone_number: str
    bank_name: Optional[str] = None
    status: str
    requested_at: datetime
    processed_at: Optional[datetime] = None
    unique_users_count: int
    
    model_config = {"from_attributes": True}


class PaymentProcessRequest(BaseModel):
    status: str = Field(..., pattern="^(completed|rejected)$") 