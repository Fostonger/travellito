from fastapi import APIRouter
import stripe, os, uuid
from sqlalchemy import select
from .models import Tour, User, Referral
from .deps import SessionDep

router = APIRouter()

@router.post("/buy")
async def buy(session: SessionDep, payload: dict):
    tour   = await session.get(Tour, payload["tour_id"])
    user   = await session.get(User, payload["user_id"])
    ref    = await session.scalar(select(Referral)
             .where(Referral.user_id==user.id))
    landlord_id = ref.landlord_id if ref else None
    checkout = stripe.checkout.Session.create(
        client_reference_id=str(user.id),
        metadata={
            "landlord_id": landlord_id or "",
            "tour_id": tour.id,
            "qty": 1
        },
        line_items=[{
            "name": tour.title,
            "quantity": 1,
            "currency": "eur",
            "amount": int(tour.price * 100)
        }],
        success_url=os.getenv("SUCCESS_URL", "https://t.me/"+os.getenv("BOT_ALIAS")),
        mode="payment"
    )
    return {"checkout_url": checkout.url}