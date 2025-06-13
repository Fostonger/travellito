from __future__ import annotations

import os
import asyncio
from typing import Sequence

from fastapi import APIRouter, HTTPException, Depends, Path, status, BackgroundTasks
from sqlalchemy import select
import httpx
from pydantic import BaseModel, Field

from ..deps import Session, SessionDep
from ..models import Purchase, User, Departure, Tour
from ..security import role_required, current_user

router = APIRouter(prefix="/departures", tags=["broadcast"])

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var must be set for broadcast")


class BroadcastBody(BaseModel):
    text: str | None = Field(None, max_length=4096)
    photo_url: str | None = None
    document_url: str | None = None

    model_config = {
        "extra": "forbid",
    }


async def _do_broadcast(dep_id: int, message: BroadcastBody):
    """Background task that fetches chat_ids and sends messages via Telegram."""

    async with Session() as sess:
        # Join Purchase ➜ User to retrieve Telegram chat IDs
        stmt = (
            select(User.tg_id)
            .join(Purchase, Purchase.user_id == User.id)
            .where(Purchase.departure_id == dep_id)
        )
        result = await sess.scalars(stmt)
        chat_ids: Sequence[int] = list(result)

    if not chat_ids:
        # No bookings – nothing to do
        return

    api = f"https://api.telegram.org/bot{BOT_TOKEN}"

    async with httpx.AsyncClient() as client:
        rate_limit = 25  # msgs per second (Telegram limit 30)

        async def _send(chat_id: int):
            if message.text:
                await client.post(f"{api}/sendMessage", json={"chat_id": chat_id, "text": message.text})
            if message.photo_url:
                await client.post(f"{api}/sendPhoto", json={"chat_id": chat_id, "photo": message.photo_url})
            if message.document_url:
                await client.post(f"{api}/sendDocument", json={"chat_id": chat_id, "document": message.document_url})

        # Send sequentially obeying rate-limit
        for i, cid in enumerate(chat_ids):
            await _send(cid)
            if (i + 1) % rate_limit == 0:
                await asyncio.sleep(1)


@router.post("/{departure_id}/broadcast", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(role_required(["bot", "manager"]))])
async def broadcast(
    background_tasks: BackgroundTasks,
    sess: SessionDep,
    departure_id: int = Path(..., gt=0),
    payload: BroadcastBody | None = None,
    user=Depends(current_user),
):
    """Asynchronously broadcast *payload* to every tourist booked on the departure."""

    if payload is None or not any([payload.text, payload.photo_url, payload.document_url]):
        raise HTTPException(400, "Payload cannot be empty")

    # -----------------------------
    # Ownership check (manager role)
    # -----------------------------
    if user["role"] == "manager":
        # Fetch departure & related tour
        dep: Departure | None = await sess.get(Departure, departure_id)
        if not dep:
            raise HTTPException(404, "Departure not found")
        tour: Tour | None = await sess.get(Tour, dep.tour_id)
        if not tour:
            raise HTTPException(404, "Tour not found")

        manager: User | None = await sess.get(User, int(user["sub"]))
        if not manager or manager.agency_id is None or manager.agency_id != tour.agency_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed for this departure")

    # Schedule background send so we respond quickly
    background_tasks.add_task(_do_broadcast, departure_id, payload)

    return {"scheduled": True}

# ---------- Manager departures listing ----------
from pydantic import BaseModel
from datetime import datetime as _dt

class DepartureOut(BaseModel):
    id: int
    tour_title: str
    starts_at: _dt

    model_config = {
        "from_attributes": True,
    }

@router.get("/", response_model=list[DepartureOut], dependencies=[Depends(role_required(["admin", "bot", "manager"]))])
async def list_departures(sess: SessionDep, user=Depends(current_user)):
    """Return upcoming departures with at least one booking.

    • Admin / bot roles ⇒ all departures.
    • Manager ⇒ only departures belonging to their agency.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # Base query: departures in the future with bookings > 0
    stmt = (
        select(Departure.id, Tour.title, Departure.starts_at)
        .join(Tour, Tour.id == Departure.tour_id)
        .join(Purchase, Purchase.departure_id == Departure.id)
        .where(Departure.starts_at >= now)
        .group_by(Departure.id, Tour.title, Departure.starts_at)
        .order_by(Departure.starts_at.asc())
    )

    # Restrict to manager's agency if needed
    if user["role"] == "manager":
        mgr: User | None = await sess.get(User, int(user["sub"]))
        if not mgr or mgr.agency_id is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Manager not linked to any agency")
        stmt = stmt.where(Tour.agency_id == mgr.agency_id)

    rows = await sess.execute(stmt)
    return [DepartureOut(id=d_id, tour_title=title, starts_at=starts) for d_id, title, starts in rows] 