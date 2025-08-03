from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from .support_schemas import UserInfo

class LoginRequest(BaseModel):
    """Schema for login request"""
    email: EmailStr
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Schema for login response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Schema for refresh token response"""
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Schema for change password request"""
    current_password: str
    new_password: str = Field(..., min_length=6)


class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr
    password: str = Field(..., min_length=6)
    first: Optional[str] = Field(None, max_length=64)
    last: Optional[str] = Field(None, max_length=64)
    role: str
    agency_id: Optional[int] = None


class UserOut(BaseModel):
    """Schema for user response"""
    id: int
    email: str
    role: str
    first: Optional[str] = None
    last: Optional[str] = None
    agency_id: Optional[int] = None

    model_config = {
        "from_attributes": True,
    }


class TelegramInitRequest(BaseModel):
    """Schema for Telegram WebApp initData authentication request"""
    init_data: str = Field(..., description="Raw initData string from Telegram.WebApp.initData")


class TelegramAuthResponse(BaseModel):
    """Response data for Telegram WebApp authentication."""
    user: UserInfo
    access_token: str
    refresh_token: str

class TelegramUserAuth(BaseModel):
    """Request schema for direct Telegram user authentication."""
    telegram_user: dict