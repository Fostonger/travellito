from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from decimal import Decimal
from sqlalchemy import select, func, delete as _delete

from ..security import role_required
from ..deps import SessionDep
from ..models import Agency, Landlord, Tour, Departure, Purchase, ApiKey, User

from secrets import token_hex

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(role_required("admin"))])


class MaxCommissionBody(BaseModel):
    pct: Decimal = Field(..., ge=0, le=100)


class MetricsOut(BaseModel):
    agencies: int
    landlords: int
    tours: int
    departures: int
    bookings: int
    tickets_sold: int
    sales_amount: Decimal


@router.patch("/tours/{tour_id}/max-commission")
async def set_max_commission(
    sess: SessionDep,
    tour_id: int = Path(..., gt=0),
    body: MaxCommissionBody | None = None,
):
    if body is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tour not found")

    tour.max_commission_pct = body.pct
    await sess.commit()

    return MaxCommissionBody(pct=Decimal(tour.max_commission_pct))


@router.get("/metrics")
async def metrics(sess: SessionDep):
    agencies = await sess.scalar(select(func.count()).select_from(Agency)) or 0
    landlords = await sess.scalar(select(func.count()).select_from(Landlord)) or 0
    tours = await sess.scalar(select(func.count()).select_from(Tour)) or 0
    departures = await sess.scalar(select(func.count()).select_from(Departure)) or 0
    bookings = await sess.scalar(select(func.count()).select_from(Purchase)) or 0

    tickets_sold = await sess.scalar(select(func.coalesce(func.sum(Purchase.qty), 0))) or 0
    sales_amount_raw = await sess.scalar(select(func.coalesce(func.sum(Purchase.amount), 0))) or 0

    return MetricsOut(
        agencies=agencies,
        landlords=landlords,
        tours=tours,
        departures=departures,
        bookings=bookings,
        tickets_sold=tickets_sold,
        sales_amount=Decimal(sales_amount_raw).quantize(Decimal("0.01")),
    )


# ---------------------------------------------------------------------------
#  API Keys CRUD (admin only)
# ---------------------------------------------------------------------------


class ApiKeyOut(BaseModel):
    id: int
    agency_id: int
    key: str

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    agency_id: int = Field(..., gt=0)


@router.post("/api-keys", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(payload: ApiKeyCreate, sess: SessionDep):
    # Ensure agency exists
    agency: Agency | None = await sess.get(Agency, payload.agency_id)
    if not agency:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agency not found")

    api_key = ApiKey(agency_id=payload.agency_id, key=token_hex(32))
    sess.add(api_key)
    await sess.flush()
    await sess.commit()

    return ApiKeyOut.from_orm(api_key)


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(sess: SessionDep, limit: int = 100, offset: int = 0):
    stmt = (
        select(ApiKey)
        .order_by(ApiKey.created.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await sess.scalars(stmt)).all()
    return [ApiKeyOut.from_orm(r) for r in rows]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(sess: SessionDep, key_id: int):
    stmt = _delete(ApiKey).where(ApiKey.id == key_id)
    result = await sess.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")
    await sess.commit()


# ---------------------------------------------------------------------------
#  USER MANAGEMENT (minimal CRUD)
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    id: int
    email: str | None = None
    role: str
    first: str | None = None
    last: str | None = None
    tg_id: int | None = None
    agency_id: int | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = Field(..., pattern="^(admin|agency|landlord|manager)$")
    agency_id: int | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None
    role: str | None = Field(None, pattern="^(admin|agency|landlord|manager)$")
    agency_id: int | None = None


from ..api.auth import hash_password


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, sess: SessionDep):
    # Unique email check
    existing = await sess.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(400, "Email already exists")

    u = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        agency_id=payload.agency_id,
    )
    sess.add(u)
    await sess.commit()
    await sess.refresh(u)
    return UserOut.from_orm(u)


@router.get("/users", response_model=list[UserOut])
async def list_users(sess: SessionDep, limit: int = 100, offset: int = 0):
    rows = (await sess.scalars(select(User).order_by(User.id.desc()).limit(limit).offset(offset))).all()
    return [UserOut.from_orm(r) for r in rows]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: int, payload: UserUpdate, sess: SessionDep):
    user: User | None = await sess.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(user, k, v)

    await sess.commit()
    await sess.refresh(user)
    return UserOut.from_orm(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, sess: SessionDep):
    u: User | None = await sess.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    await sess.delete(u)
    await sess.commit()
    return None 