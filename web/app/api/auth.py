import os
from fastapi import APIRouter, HTTPException, Request, Response, Depends, status
from aiogram.utils.auth_widget import check_integrity
from passlib.hash import argon2
from sqlalchemy import select
from pydantic import BaseModel

from ..security import (
    mint_tokens,
    decode_token,
    ACCESS_TOKEN_EXP_SECONDS,
    REFRESH_TOKEN_EXP_SECONDS,
    current_user,
)
from ..models import User
from ..deps import Session, SessionDep
from ..roles import Role

TOKEN = os.getenv("BOT_TOKEN")

router = APIRouter(tags=["auth"])

# ---------------------------------------------------------------------------
#  Password hashing helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Return argon2 hash of *password*."""
    return argon2.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return argon2.verify(plain, hashed)


@router.get("/telegram", summary="Telegram login handshake (tourists)")
async def telegram_auth(request: Request, resp: Response):
    """Validate Telegram auth data and mint a session JWT cookie."""
    data = dict(request.query_params)
    if not check_integrity(TOKEN, data):
        raise HTTPException(400, "Bad signature")

    async with Session() as s, s.begin():
        user = await User.get_or_create(s, data, role=Role.bot_user)

    # Bot users interact via the Telegram bot, but from the web POV they are
    # simple authenticated end-users with role "bot_user".

    extra = {}
    if user.role in ("agency", "manager") and user.agency_id is not None:
        extra["agency_id"] = user.agency_id

    access_tok, refresh_tok = mint_tokens(user.id, user.role, **extra)

    # Short-lived access token for API calls
    resp.set_cookie(
        "session",
        access_tok,
        max_age=ACCESS_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    # Longer-lived refresh token; issued as HttpOnly so it's inaccessible to JS
    resp.set_cookie(
        "refresh_token",
        refresh_tok,
        max_age=REFRESH_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    # Return tokens in the JSON payload so non-browser clients (e.g. the Telegram bot) can consume them directly
    return {
        "ok": True,
        "access_token": access_tok,
        "refresh_token": refresh_tok,
        "role": user.role,
    }


# ---------------------------------------------------------------------------
#  Token Refresh – silently renew access cookie if refresh token is valid
# ---------------------------------------------------------------------------


@router.post("/refresh", summary="Exchange a refresh_token cookie for a new access JWT")
async def refresh_token(request: Request, response: Response):
    refresh_tok: str | None = request.cookies.get("refresh_token")
    if not refresh_tok:
        raise HTTPException(401, "Missing refresh token")

    payload = decode_token(refresh_tok)

    # Create and set new pair (rotate tokens)
    extra = {}
    if payload.get("role") in ("agency", "manager") and payload.get("agency_id") is not None:
        extra["agency_id"] = payload["agency_id"]

    access_tok, new_refresh_tok = mint_tokens(payload["sub"], payload["role"], **extra)

    response.set_cookie(
        "session",
        access_tok,
        max_age=ACCESS_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    response.set_cookie(
        "refresh_token",
        new_refresh_tok,
        max_age=REFRESH_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return {"refreshed": True}


# ---------------------------------------------------------------------------
#  Telegram auth for Tour MANAGERS – identical flow but role = manager
# ---------------------------------------------------------------------------


@router.get("/telegram/manager", summary="Telegram login for tour managers")
async def telegram_manager_auth(request: Request, resp: Response):
    data = dict(request.query_params)
    if not check_integrity(TOKEN, data):
        raise HTTPException(400, "Bad signature")

    agency_id: int | None = None
    if "agency_id" in data:
        try:
            agency_id = int(data["agency_id"])
        except ValueError:
            raise HTTPException(400, "Invalid agency_id")

    async with Session() as s, s.begin():
        user = await User.get_or_create(s, data, role=Role.manager)

        # Persist agency affiliation if supplied
        if agency_id is not None:
            user.agency_id = agency_id

    extra = {}
    if user.agency_id is not None:
        extra["agency_id"] = user.agency_id

    access_tok, refresh_tok = mint_tokens(user.id, Role.manager.value, **extra)

    resp.set_cookie(
        "session",
        access_tok,
        max_age=ACCESS_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    resp.set_cookie(
        "refresh_token",
        refresh_tok,
        max_age=REFRESH_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return {"ok": True}


# ---------------------------------------------------------------------------
#  Email / password login for admin, agency, landlord, etc.
# ---------------------------------------------------------------------------


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/login", summary="Email/password login", status_code=status.HTTP_200_OK)
async def email_login(payload: LoginIn, response: Response, sess: SessionDep):
    stmt = select(User).where(User.email == payload.email)
    user: User | None = await sess.scalar(stmt)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    extra = {}
    if user.role in ("agency", "manager") and user.agency_id is not None:
        extra["agency_id"] = user.agency_id

    access_tok, refresh_tok = mint_tokens(user.id, user.role, **extra)

    response.set_cookie(
        "session",
        access_tok,
        max_age=ACCESS_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    response.set_cookie(
        "refresh_token",
        refresh_tok,
        max_age=REFRESH_TOKEN_EXP_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return {"role": user.role}


# ---------------------------------------------------------------------------
#  Logout – clear cookies (refresh token rotation blacklist TODO)
# ---------------------------------------------------------------------------


@router.post("/logout", summary="Sign out user and clear cookies", status_code=status.HTTP_204_NO_CONTENT)
async def logout(resp: Response):
    resp.delete_cookie("session")
    resp.delete_cookie("refresh_token")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
#  Current user helper – handy for WebApp bootstrapping
# ---------------------------------------------------------------------------

class MeOut(BaseModel):
    """Minimal user payload returned by `/auth/me`."""

    id: int
    role: str
    tg_id: int | None = None
    first: str | None = None
    last: str | None = None
    agency_id: int | None = None


@router.get("/me", response_model=MeOut, summary="Return the currently authenticated user")
async def me(sess: SessionDep, user=Depends(current_user)):
    """Return basic information about the current session user.

    Useful for the Telegram WebApp right after the auth handshake to display
    the user name or decide which UI (tourist vs manager) to load.
    """
    u: User | None = await sess.get(User, int(user["sub"]))
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    return MeOut(
        id=u.id,
        role=u.role,
        tg_id=u.tg_id,
        first=u.first,
        last=u.last,
        agency_id=u.agency_id,
    )


# ---------------------------------------------------------------------------
#  Telegram auth from bot (no widget integrity check)
# ---------------------------------------------------------------------------

class TelegramUserData(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    auth_date: int | None = None
    hash: str | None = None


@router.post("/telegram/bot", summary="Telegram auth directly from bot")
async def telegram_bot_auth(user_data: TelegramUserData, resp: Response):
    """Authenticate a user directly from the Telegram bot.
    
    This endpoint is only called by our bot backend, not by clients.
    It creates or retrieves a user and returns tokens without requiring
    the Telegram login widget hash verification.
    """
    # Convert to format expected by User.get_or_create
    tg_data = {
        "id": user_data.id,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "username": user_data.username,
    }
    
    async with Session() as s, s.begin():
        user = await User.get_or_create(s, tg_data, role=Role.bot_user)

    extra = {}
    if user.role in ("agency", "manager") and user.agency_id is not None:
        extra["agency_id"] = user.agency_id

    access_tok, refresh_tok = mint_tokens(user.id, user.role, **extra)

    # Return tokens in the JSON payload for the bot to store
    return {
        "ok": True,
        "access_token": access_tok,
        "refresh_token": refresh_tok,
        "role": user.role,
        "user_id": user.id
    }


@router.post("/telegram/webapp", summary="Telegram WebApp auth")
async def telegram_webapp_auth(user_data: TelegramUserData, resp: Response):
    """Authenticate a user from the Telegram WebApp.
    
    This endpoint is called by the WebApp running in the Telegram client.
    It creates or retrieves a user and returns tokens.
    """
    # Convert to format expected by User.get_or_create
    tg_data = {
        "id": user_data.id,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "username": user_data.username,
    }
    
    async with Session() as s, s.begin():
        user = await User.get_or_create(s, tg_data, role=Role.bot_user)

    extra = {}
    if user.role in ("agency", "manager") and user.agency_id is not None:
        extra["agency_id"] = user.agency_id

    access_tok, refresh_tok = mint_tokens(user.id, user.role, **extra)

    # Return tokens in the JSON payload for the WebApp to store
    return {
        "ok": True,
        "access_token": access_tok,
        "refresh_token": refresh_tok,
        "role": user.role,
        "user_id": user.id
    } 