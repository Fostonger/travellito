from __future__ import annotations

import os
import time
from typing import Annotated, Callable, Iterable

from fastapi import Depends, HTTPException, Request, status, Header
from jose import JWTError, jwt
from .roles import Role
from .deps import SessionDep
from sqlalchemy import select

# ---------------------------------------------------------------------------
#  Basic JWT helpers
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # In development, use a default key, but warn about it
    SECRET_KEY = "insecure-dev-key-do-not-use-in-production"
    print("WARNING: Using default SECRET_KEY. This is insecure for production!")

ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
#  Token lifetime configuration – override via env vars
# ---------------------------------------------------------------------------

# Short-lived access token (default 15 min) and longer refresh token (default 30 days)
ACCESS_TOKEN_EXP_SECONDS: int = int(os.getenv("JWT_ACCESS_TTL", "900"))  # 15 minutes
REFRESH_TOKEN_EXP_SECONDS: int = int(os.getenv("JWT_REFRESH_TTL", str(60 * 60 * 24 * 30)))  # 30 days

# Fallback used by create_token when custom expires_in passed
DEFAULT_EXP_SECONDS = ACCESS_TOKEN_EXP_SECONDS


def _now() -> int:
    return int(time.time())


def create_token(
    sub: int | str,
    role: str,
    *,
    expires_in: int = DEFAULT_EXP_SECONDS,
    **extra_claims,
) -> str:
    """Return a signed JWT including any *extra_claims*.

    Standard claims:
    • sub  – user identifier
    • role – user role string
    • exp  – expiry (unix epoch)

    Additional keyword arguments are merged into the payload, letting callers
    embed e.g. ``agency_id`` for agency / manager tokens.
    """
    payload = {
        "sub": str(sub),
        "role": role,
        "exp": _now() + expires_in,
    }
    payload.update(extra_claims)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Verify *token* and return its payload."""
    try:
        payload: dict = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
    return payload


# ---------------------------------------------------------------------------
#  Dependencies
# ---------------------------------------------------------------------------
async def _extract_token(req: Request) -> str | None:
    """Return JWT from Authorization header *or* access_token/session cookie."""
    # Priority: Authorization: Bearer <token>
    auth: str | None = req.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    
    # Then try the new access_token cookie (preferred for WebApp)
    access_token = req.cookies.get("access_token")
    if access_token:
        return access_token
    
    # Fallback to legacy session cookie (browser flows)
    return req.cookies.get("session")


async def current_user(req: Request) -> dict:
    """FastAPI dependency returning the JWT payload or raises 401."""
    token = await _extract_token(req)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")
    return decode_token(token)


def _to_role_str(value: "str | Role") -> str:
    """Return the *string* value of a Role or raw str."""
    if isinstance(value, Role):
        return value.value
    return str(value)


def role_required(*allowed: "str | Role | Iterable[str | Role]") -> Callable[[dict], dict]:
    """Return a dependency that checks *current_user* role is within *allowed*.

    Usage:
        @router.get("/admin", dependencies=[Depends(role_required("admin"))])
        async def admin_only():
            ...
    """
    # Flatten iterables (allow role_required([Role.admin, Role.agency]))
    if len(allowed) == 1 and isinstance(allowed[0], (list, tuple, set)):
        allowed = tuple(allowed[0])
    # Normalise to strings
    allowed_set = {_to_role_str(a) for a in allowed}

    async def _dep(user: Annotated[dict, Depends(current_user)]):
        role: str | None = user.get("role")
        if role not in allowed_set:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return _dep


# Convenience helper: returns *(access, refresh)* tokens pair
def mint_tokens(sub: int | str, role: str, **extra_claims) -> tuple[str, str]:
    """Return *(access, refresh)* pair embedding *extra_claims* in both."""
    access = create_token(
        sub,
        role,
        expires_in=ACCESS_TOKEN_EXP_SECONDS,
        **extra_claims,
    )
    refresh = create_token(
        sub,
        role,
        expires_in=REFRESH_TOKEN_EXP_SECONDS,
        **extra_claims,
    )
    return access, refresh


# ---------------------------------------------------------------------------
#  API Key authentication (admin-created keys for external agency sync)
# ---------------------------------------------------------------------------

async def require_api_key(
    sess: SessionDep,
    api_key: str | None = Header(None, alias="X-API-Key"),
):
    """FastAPI dependency that raises 401 unless *api_key* matches a row in ApiKey."""
    if api_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    # Local import to avoid circular dependency
    from .models import ApiKey

    stmt = select(ApiKey).where(ApiKey.key == api_key)
    res = await sess.scalar(stmt)
    if res is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return res 