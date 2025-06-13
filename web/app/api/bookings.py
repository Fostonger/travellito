from __future__ import annotations

from decimal import Decimal
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from ..deps import SessionDep
from ..locks import SeatLock
from ..models import Departure, Purchase, Referral, Tour, TicketCategory, PurchaseItem, LandlordCommission
from ..security import role_required, current_user
from .public import HUNDRED  # reuse constant

router = APIRouter(prefix="/bookings", tags=["bookings"])


# ---------------------------------------------------------------------------
#  Schemas
# ---------------------------------------------------------------------------
class Item(BaseModel):
    category_id: int = Field(..., gt=0)
    qty: int = Field(1, gt=0)


class BookingCreate(BaseModel):
    departure_id: int = Field(..., gt=0)
    items: list[Item] = Field(..., min_items=1)

    @field_validator("items")
    def non_empty(cls, v):
        if not v:
            raise ValueError("Items cannot be empty")
        return v


class BookingUpdate(BaseModel):
    # Provide new items list; empty list → cancel
    items: Optional[list[Item]] = None


class BookingOut(BaseModel):
    id: int
    amount_gross: Decimal
    amount: Decimal
    items: list[Item]

    model_config = {
        "from_attributes": True,
    }


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

async def _seats_taken(sess: SessionDep, departure_id: int) -> int:
    stmt = (
        select(func.coalesce(func.sum(PurchaseItem.qty), 0))
        .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
        .where(Purchase.departure_id == departure_id)
    )
    taken: int = await sess.scalar(stmt)
    return taken or 0


# ---------------------------------------------------------------------------
#  End-points
# ---------------------------------------------------------------------------


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(role_required("bot_user"))])
async def create_booking(payload: BookingCreate, sess: SessionDep, user=Depends(current_user)):
    """Persist a new booking for the current tourist.

    – Verifies capacity.
    – Applies any landlord referral.
    – Stores total amount (price × qty; commission/discount not yet applied).
    """
    # Acquire short-lived Redis mutex in addition to DB row-lock for UX-friendly retries
    async with SeatLock(payload.departure_id):
        # Lock departure row to avoid race conditions on capacity
        stmt_dep = (
            select(Departure)
            .options(selectinload(Departure.tour))
            .where(Departure.id == payload.departure_id)
            .with_for_update()
        )
        dep: Departure | None = await sess.scalar(stmt_dep)
        if not dep:
            raise HTTPException(404, "Departure not found")

        # Check seats availability
        taken = await _seats_taken(sess, dep.id)
        total_qty = sum(i.qty for i in payload.items)
        remaining = dep.capacity - taken
        if remaining < total_qty:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Not enough seats available")

        # Determine landlord via last referral (if any)
        stmt_ref = (
            select(Referral.landlord_id)
            .where(Referral.user_id == int(user["sub"]))
            .order_by(Referral.ts.desc())
            .limit(1)
        )
        landlord_id: int | None = await sess.scalar(stmt_ref)

        # Fetch chosen commission for landlord & tour (if set)
        commission_pct: Decimal | None = None
        if landlord_id is not None:
            stmt_comm = select(LandlordCommission.commission_pct).where(
                LandlordCommission.landlord_id == landlord_id,
                LandlordCommission.tour_id == dep.tour_id,
            )
            commission_pct = await sess.scalar(stmt_comm)

        # Fallback to zero commission if not configured
        commission_pct = commission_pct or Decimal("0")

        # Ensure does not exceed max (could happen if tour reduced its max later)
        if commission_pct > dep.tour.max_commission_pct:
            commission_pct = dep.tour.max_commission_pct

        # Validate categories belong to tour & compute NET amount applying discount
        categories_stmt = select(TicketCategory).where(TicketCategory.tour_id == dep.tour_id)
        cat_list = (await sess.scalars(categories_stmt)).all()
        cat_map = {c.id: c for c in cat_list}

        # Discount logic
        discount_pct = (dep.tour.max_commission_pct - commission_pct).quantize(Decimal("0.01"))
        if discount_pct < 0:
            discount_pct = Decimal("0")

        amount_net = Decimal("0.00")
        amount_gross = Decimal("0.00")

        for it in payload.items:
            cat = cat_map.get(it.category_id)
            if not cat:
                raise HTTPException(400, "Category does not belong to tour")
            line_gross = cat.price * it.qty
            amount_gross += line_gross
            line_net = (cat.price * (HUNDRED - discount_pct) / HUNDRED) * it.qty
            amount_net += line_net

        purchase = Purchase(
            user_id=int(user["sub"]),
            departure_id=dep.id,
            landlord_id=landlord_id,
            qty=total_qty,
            amount_gross=amount_gross,
            amount=amount_net,
            commission_pct=commission_pct,
        )
        sess.add(purchase)
        await sess.flush()  # obtain purchase.id

        # Insert PurchaseItem rows
        for it in payload.items:
            cat = cat_map[it.category_id]
            sess.add(PurchaseItem(
                purchase_id=purchase.id,
                category_id=it.category_id,
                qty=it.qty,
                amount=(cat.price * (HUNDRED - discount_pct) / HUNDRED) * it.qty,
            ))

        # Commit to save all changes
        await sess.commit()

        out_items = [Item(category_id=pi.category_id, qty=pi.qty) for pi in purchase.items]
        return BookingOut(id=purchase.id, amount_gross=purchase.amount_gross, amount=purchase.amount, items=out_items)


@router.patch("/{booking_id}", response_model=BookingOut,
              dependencies=[Depends(role_required("bot_user"))])
async def update_booking(
    booking_id: int,
    payload: BookingUpdate,
    sess: SessionDep,
    user=Depends(current_user),
):
    """Change quantity or cancel a booking owned by the current user."""
    # First fetch departure_id to compose lock key
    dep_id_stmt = select(Purchase.departure_id).where(Purchase.id == booking_id)
    dep_id: int | None = await sess.scalar(dep_id_stmt)
    # If booking not found we defer to the normal path below
    async with SeatLock(dep_id or 0):
        # Fetch booking + lock row
        stmt = (
            select(Purchase)
            .join(Departure)
            .options(selectinload(Purchase.departure).selectinload(Departure.tour))
            .where(Purchase.id == booking_id)
            .with_for_update()
        )
        purchase: Purchase | None = await sess.scalar(stmt)
        if not purchase:
            raise HTTPException(404, "Booking not found")

    # ------------------------------------------------------------------
    #  Enforce free-cancellation cutoff
    # ------------------------------------------------------------------
    tour_cutoff_h = purchase.departure.tour.free_cancellation_cutoff_h
    cutoff_ts = purchase.departure.starts_at - timedelta(hours=tour_cutoff_h)
    if datetime.utcnow() >= cutoff_ts:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Modification window closed – past free-cancellation cutoff")

    if purchase.user_id != int(user["sub"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot modify others' bookings")

    if payload.items is None:
        new_items: list[Item] = []  # cancel
    else:
        new_items = payload.items

    new_total_qty = sum(i.qty for i in new_items)

    delta = new_total_qty - purchase.qty

    if new_total_qty == 0:
        await sess.delete(purchase)
        await sess.commit()
        return BookingOut(id=booking_id, amount_gross=Decimal("0.00"), amount=Decimal("0.00"), items=[])

    # Capacity check
    taken = await _seats_taken(sess, purchase.departure_id)
    remaining = purchase.departure.capacity - (taken - purchase.qty)  # exclude current booking
    if delta > 0 and remaining < delta:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Not enough seats available for increase")

    # Validate categories and update items
    categories_stmt = select(TicketCategory).where(TicketCategory.tour_id == purchase.departure.tour_id)
    cat_list = (await sess.scalars(categories_stmt)).all()
    cat_map = {c.id: c for c in cat_list}

    # Recompute net amount applying discount already stored in purchase.commission_pct
    discount_pct = (purchase.departure.tour.max_commission_pct - (purchase.commission_pct or Decimal("0"))).quantize(Decimal("0.01"))
    if discount_pct < 0:
        discount_pct = Decimal("0")

    amount_net = Decimal("0.00")
    amount_gross = Decimal("0.00")

    # Build map for new_items
    new_map = {it.category_id: it for it in new_items}

    # Iterate existing items, delete or update
    for pi in list(purchase.items):
        if pi.category_id not in new_map:
            await sess.delete(pi)
        else:
            it = new_map.pop(pi.category_id)
            cat = cat_map.get(it.category_id)
            if not cat:
                raise HTTPException(400, "Invalid category")
            pi.qty = it.qty
            net_line = (cat.price * (HUNDRED - discount_pct) / HUNDRED) * it.qty
            pi.amount = net_line
            amount_net += net_line
            amount_gross += cat.price * it.qty

    # Add remaining new items
    for it in new_map.values():
        cat = cat_map.get(it.category_id)
        if not cat:
            raise HTTPException(400, "Invalid category")
        sess.add(PurchaseItem(
            purchase_id=purchase.id,
            category_id=it.category_id,
            qty=it.qty,
            amount=(cat.price * (HUNDRED - discount_pct) / HUNDRED) * it.qty,
        ))
        amount_net += (cat.price * (HUNDRED - discount_pct) / HUNDRED) * it.qty
        amount_gross += cat.price * it.qty

    purchase.qty = new_total_qty
    purchase.amount_gross = amount_gross
    purchase.amount = amount_net

    await sess.commit()

    return BookingOut(
        id=purchase.id,
        amount_gross=purchase.amount_gross,
        amount=purchase.amount,
        items=[Item(category_id=pi.category_id, qty=pi.qty) for pi in purchase.items],
    )


@router.get("/", response_model=list[BookingOut], dependencies=[Depends(role_required("bot_user"))])
async def list_bookings(
    sess: SessionDep,
    limit: int = 50,
    offset: int = 0,
    user=Depends(current_user),
):
    """Return bookings owned by the current tourist sorted by most recent first."""
    stmt = (
        select(Purchase)
        .options(selectinload(Purchase.items))
        .where(Purchase.user_id == int(user["sub"]))
        .order_by(Purchase.ts.desc())
        .limit(limit)
        .offset(offset)
    )
    purchases = (await sess.scalars(stmt)).unique().all()

    out: list[BookingOut] = []
    for p in purchases:
        out_items = [Item(category_id=it.category_id, qty=it.qty) for it in p.items]
        out.append(
            BookingOut(
                id=p.id,
                amount_gross=p.amount_gross,
                amount=p.amount,
                items=out_items,
            )
        )
    return out 