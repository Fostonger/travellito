from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.api.v1.schemas.auth_schemas import (
    LoginRequest, LoginResponse, RefreshTokenRequest, RefreshTokenResponse,
    ChangePasswordRequest, UserOut
)
from app.deps import SessionDep
from app.services.auth_service import AuthService
from app.security import current_user


router = APIRouter()

# OAuth2 scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


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
    form_data: OAuth2PasswordRequestForm = Depends(),
    sess: SessionDep = Depends()
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
    payload: RefreshTokenRequest,
    sess: SessionDep
):
    """Get new access token using refresh token"""
    service = AuthService(sess)
    
    access_token = await service.refresh_access_token(payload.refresh_token)
    
    return RefreshTokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response):
    """Logout (clear session cookie)"""
    response.delete_cookie(key="session")
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