from fastapi import APIRouter, Depends, Response, status, HTTPException, Security, Cookie
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPBasic, HTTPBasicCredentials
import os
import secrets
import time
import json
from typing import Dict, Optional
import logging
from datetime import datetime

from app.api.v1.schemas.auth_schemas import (
    LoginRequest, LoginResponse, RefreshTokenRequest, RefreshTokenResponse,
    ChangePasswordRequest, UserOut, TelegramInitRequest, TelegramAuthResponse
)
from app.deps import SessionDep
from app.services.auth_service import AuthService
from app.security import current_user, decode_token, ACCESS_TOKEN_EXP_SECONDS, REFRESH_TOKEN_EXP_SECONDS
from app.api.v1.utils import verify_telegram_webapp_data
from app.models import User, ReferralEvent


router = APIRouter()

# OAuth2 scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Basic auth for token introspection
security = HTTPBasic()


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    sess: SessionDep
):
    """Login with email and password"""
    service = AuthService(sess)
    
    user, access_token, refresh_token = await service.authenticate_user(
        email=payload.email,
        password=payload.password
    )
    
    # Set cookie for browser-based auth
    response.set_cookie(
        key="session",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 15  # 15 minutes
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "first": user.first,
            "last": user.last,
            "agency_id": user.agency_id
        }
    )


@router.post("/token", response_model=LoginResponse)
async def login_for_token(
    sess: SessionDep,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """OAuth2 compatible token endpoint for Swagger UI"""
    service = AuthService(sess)
    
    user, access_token, refresh_token = await service.authenticate_user(
        email=form_data.username,  # OAuth2 spec uses 'username'
        password=form_data.password
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "first": user.first,
            "last": user.last,
            "agency_id": user.agency_id
        }
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    response: Response,
    sess: SessionDep,
    refresh_token: Optional[str] = Cookie(None),
    payload: Optional[RefreshTokenRequest] = None
):
    """
    Get new access token using refresh token
    
    This endpoint accepts refresh token either from cookie (preferred) or from request body.
    It returns a new access token and sets it as a cookie.
    """
    service = AuthService(sess)
    
    # Get refresh token from cookie or request body
    token = refresh_token
    if not token and payload and payload.refresh_token:
        token = payload.refresh_token
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    
    # Refresh the token
    access_token = await service.refresh_access_token(token)
    
    # Set cookie for browser-based auth
    cookie_domain = os.getenv("COOKIE_DOMAIN", None)
    cookie_secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite="none",  # Required for WebApp embedded in Telegram
        max_age=ACCESS_TOKEN_EXP_SECONDS,
        domain=cookie_domain
    )
    
    # Return token for API clients
    return RefreshTokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response):
    """Logout (clear auth cookies)"""
    cookie_domain = os.getenv("COOKIE_DOMAIN", None)
    
    # Clear both cookies
    response.delete_cookie(key="access_token", domain=cookie_domain, samesite="none")
    response.delete_cookie(key="refresh_token", domain=cookie_domain, samesite="none")
    
    # For backward compatibility
    response.delete_cookie(key="session", domain=cookie_domain)
    
    return {"success": True}


@router.post("/change-password", response_model=UserOut)
async def change_password(
    payload: ChangePasswordRequest,
    sess: SessionDep,
    user=Depends(current_user)
):
    """Change current user's password"""
    service = AuthService(sess)
    
    updated_user = await service.change_password(
        user_id=int(user["sub"]),
        current_password=payload.current_password,
        new_password=payload.new_password
    )
    
    await sess.commit()
    
    return UserOut.model_validate(updated_user)


@router.get("/me", response_model=UserOut)
async def get_current_user(
    sess: SessionDep,
    user=Depends(current_user)
):
    """Get current user info"""
    from app.infrastructure.repositories import UserRepository
    
    user_repo = UserRepository(sess)
    user_obj = await user_repo.get_with_agency(int(user["sub"]))
    
    if not user_obj:
        raise Exception("User not found")
    
    return UserOut.model_validate(user_obj)


@router.post("/telegram/bot")
async def telegram_bot_auth(
    user_data: Dict,
    sess: SessionDep
):
    """Authenticate a user from Telegram bot
    
    This endpoint is called by the bot to authenticate users based on their Telegram ID.
    It creates or updates a user record and returns JWT tokens.
    
    Optional apartment_id can be provided to track user origin from QR codes.
    """
    from app.models import User
    from app.roles import Role
    from datetime import datetime
    
    if not user_data.get("id"):
        raise HTTPException(status_code=400, detail="Invalid user data")
    
    # Get or create user
    user = await User.get_or_create(
        sess, 
        user_data,
        role=Role.bot_user
    )
    
    # Handle apartment_id if provided
    apartment_id = user_data.get("apartment_id")
    if apartment_id:
        try:
            # Convert to integer (it comes as string from the bot)
            apartment_id = int(apartment_id)
            # Update apartment_id and timestamp
            user.apartment_id = apartment_id
            user.apartment_set_at = datetime.utcnow()
        except (ValueError, TypeError):
            # Log error but continue with authentication
            logging.error(f"Invalid apartment_id format: {apartment_id}")
    
    # Flush the session to ensure the user has an ID before authentication
    await sess.flush()
    
    # Generate tokens
    service = AuthService(sess)
    _, access_token, refresh_token = await service.authenticate_user_by_id(user.id)
    
    await sess.commit()
    token =  {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "role": user.role,
            "first": user.first,
            "last": user.last
        }
    }

    # TODO: remove this
    print(token)
    
    return token


@router.post("/telegram/init", response_model=TelegramAuthResponse)
async def telegram_webapp_init(
    payload: TelegramInitRequest,
    response: Response,
    sess: SessionDep
):
    """
    Authenticate a user from Telegram WebApp using initData
    
    This endpoint verifies the Telegram WebApp initData signature and issues
    JWT tokens via HttpOnly cookies.
    """
    logger = logging.getLogger("app.api.auth.telegram")
    
    # Verify initData
    is_valid, data, error = verify_telegram_webapp_data(payload.init_data)
    
    if not is_valid:
        logger.error(f"Invalid Telegram initData: {error}")
        raise HTTPException(status_code=401, detail=f"Invalid Telegram initData: {error}")
    
    # Extract user data
    user_data = {}
    if "user" in data:
        # If user data is provided as a JSON string (common in WebApp)
        try:
            user_data = json.loads(data["user"])
        except (json.JSONDecodeError, TypeError):
            logger.error("Failed to parse user data JSON")
            raise HTTPException(status_code=400, detail="Invalid user data format")
    else:
        # Extract user fields directly from the data
        for key in ["id", "first_name", "last_name", "username", "language_code"]:
            if key in data:
                user_data[key] = data[key]
    
    # Ensure we have a user ID
    if not user_data.get("id"):
        logger.error("Missing user ID in Telegram initData")
        raise HTTPException(status_code=400, detail="Missing user ID in Telegram initData")
    
    # Get or create user
    from app.models import User
    from app.roles import Role
    
    # Get or create user
    user = await User.get_or_create(
        sess, 
        user_data,
        role=Role.bot_user
    )
    
    # Handle start_param (referral) if provided
    start_param = data.get("start_param")
    if start_param and start_param.strip():
        try:
            # Convert to integer (apartment_id)
            apartment_id = int(start_param)
            
            # Record old referral for audit
            old_referral = user.apartment_id
            
            # Always overwrite apartment_id with start_param if present
            user.apartment_id = apartment_id
            user.apartment_set_at = datetime.utcnow()
            
            # Add to referral_events if the referral changed
            if old_referral != apartment_id:
                referral_event = ReferralEvent(
                    user_id=user.id,
                    old_referral=old_referral,
                    new_referral=apartment_id
                )
                sess.add(referral_event)
                
                logger.info(f"Updated referral for user {user.id}: {old_referral} -> {apartment_id}")
            
        except (ValueError, TypeError):
            # Log error but continue with authentication
            logger.error(f"Invalid start_param format: {start_param}")
    
    # Flush the session to ensure the user has an ID before authentication
    await sess.flush()
    
    # Generate tokens
    service = AuthService(sess)
    _, access_token, refresh_token = await service.authenticate_user_by_id(user.id)
    
    # Set cookies for browser-based auth
    cookie_domain = os.getenv("COOKIE_DOMAIN", None)
    cookie_secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    
    # Set access token cookie - short-lived
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite="none",  # Required for WebApp embedded in Telegram
        max_age=ACCESS_TOKEN_EXP_SECONDS,
        domain=cookie_domain
    )
    
    # Set refresh token cookie - long-lived
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite="none",  # Required for WebApp embedded in Telegram
        max_age=REFRESH_TOKEN_EXP_SECONDS,
        domain=cookie_domain
    )
    
    await sess.commit()
    
    # Return user info without tokens
    return TelegramAuthResponse(
        user={
            "id": user.id,
            "role": user.role,
            "first": user.first,
            "last": user.last
        }
    )


@router.post("/introspect")
async def introspect_token(
    token: str,
    credentials: HTTPBasicCredentials = Security(security)
):
    """Verify a token and return its claims
    
    This endpoint is protected by HTTP Basic Auth and is used to validate tokens.
    """
    # Check basic auth credentials
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "")
    
    is_correct_username = secrets.compare_digest(credentials.username, admin_user)
    is_correct_password = secrets.compare_digest(credentials.password, admin_pass)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    try:
        payload = decode_token(token)
        # Add additional validation as needed
        return {
            "active": True,
            "exp": payload.get("exp"),
            "sub": payload.get("sub"),
            "role": payload.get("role")
        }
    except Exception as e:
        return {
            "active": False,
            "error": str(e)
        } 