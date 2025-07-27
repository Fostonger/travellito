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
    refresh_token: Optional[str] = None,
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
    
    # Return token for API clients
    return RefreshTokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response):
    """Logout (clear auth cookies)"""
    
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
    
    # Log the raw initData (but mask most of it for security)
    init_data = payload.init_data
    if len(init_data) > 20:
        masked_data = init_data[:10] + "..." + init_data[-10:]
        logger.info(f"Received initData: {masked_data}")
    
    # Verify initData
    is_valid, data, error = verify_telegram_webapp_data(init_data)
    
    if not is_valid:
        logger.error(f"Invalid Telegram initData: {error}")
        raise HTTPException(status_code=401, detail=f"Invalid Telegram initData: {error}")
    
    # Extract user data
    user_data = {}
    
    # Handle different formats of user data in initData
    if "user" in data:
        # If user data is provided as a JSON string (common in WebApp)
        try:
            user_json = data["user"]
            logger.debug(f"User JSON from initData: {user_json}")
            
            # Try to parse as JSON
            try:
                user_data = json.loads(user_json)
            except json.JSONDecodeError:
                # If not valid JSON, it might be URL encoded
                logger.debug("Failed to parse as JSON, trying URL decode")
                import urllib.parse
                try:
                    decoded = urllib.parse.unquote(user_json)
                    user_data = json.loads(decoded)
                except Exception as e:
                    logger.error(f"Failed to decode user data: {e}")
                    raise HTTPException(status_code=400, detail="Invalid user data format")
        except Exception as e:
            logger.error(f"Failed to process user data: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid user data format: {str(e)}")
    else:
        # Extract user fields directly from the data
        for key in ["id", "first_name", "last_name", "username", "language_code"]:
            if key in data:
                user_data[key] = data[key]
    
    # Ensure we have a user ID
    if not user_data.get("id"):
        logger.error("Missing user ID in Telegram initData")
        raise HTTPException(status_code=400, detail="Missing user ID in Telegram initData")
    
    logger.info(f"Authenticating Telegram user: {user_data.get('id')} ({user_data.get('username', 'no username')})")
    
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
    
    logger.debug(f"Setting cookies with domain={cookie_domain}, secure={cookie_secure}")
    
    await sess.commit()
    logger.info(f"Authentication successful for Telegram user {user.id}")
    
    # Return user info without tokens
    return TelegramAuthResponse(
        user={
            "id": user.id,
            "role": user.role,
            "first": user.first,
            "last": user.last
        },
        access_token=access_token,
        refresh_token=refresh_token
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