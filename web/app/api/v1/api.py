from fastapi import APIRouter, Depends

from app.security import role_required
from app.api.v1.endpoints import (
    tours, departures, bookings, auth, admin, landlord, public, managers,
    external, broadcast, referrals
)


# Create main API router
api_v1_router = APIRouter()

# Include auth endpoints (public access)
api_v1_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

# Include tour endpoints (agency access)
api_v1_router.include_router(
    tours.router,
    prefix="/agency/tours",
    tags=["tours"],
    dependencies=[Depends(role_required("agency"))]
)

# Include departure endpoints (agency access)
api_v1_router.include_router(
    departures.router,
    prefix="/agency/departures",
    tags=["departures"],
    dependencies=[Depends(role_required("agency"))]
)

# Include booking endpoints (agency access)
api_v1_router.include_router(
    bookings.router,
    prefix="/agency/bookings",
    tags=["bookings"],
    dependencies=[Depends(role_required("agency"))]
)

# Include admin endpoints (admin access)
api_v1_router.include_router(
    admin.router,
    tags=["admin"]
)

# Include landlord endpoints (landlord access)
api_v1_router.include_router(
    landlord.router,
    prefix="/landlord",
    tags=["landlord"]
)

# Include public endpoints (public access)
api_v1_router.include_router(
    public.router,
    prefix="/public",
    tags=["public"]
)

# Include manager endpoints (agency access)
api_v1_router.include_router(
    managers.router,
    prefix="/agency",
    tags=["managers"],
    dependencies=[Depends(role_required("agency"))]
)

# Include external API endpoints (API key access)
api_v1_router.include_router(
    external.router,
    tags=["external"]
)

# Include broadcast endpoints
api_v1_router.include_router(
    broadcast.router,
    tags=["broadcast"]
)

# Include referral endpoints (bot user access)
api_v1_router.include_router(
    referrals.router,
    tags=["referrals"]
) 