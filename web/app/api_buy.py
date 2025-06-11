from fastapi import APIRouter, HTTPException

# NOTE: Stripe integration has been removed. The `buy` endpoint is kept as a
# placeholder so that the Telegram bot and other clients do not break while the
# new payment provider is being selected and implemented.

router = APIRouter()

@router.post("/buy")
async def buy():
    """TODO: Integrate with the new payment service.

    For now we simply return HTTP 501 so that callers know the feature is not
    available yet.
    """
    raise HTTPException(501, "Payment service integration pending")