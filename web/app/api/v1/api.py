from fastapi import APIRouter, Depends

from app.security import role_required
from app.api.v1.endpoints import tours, departures, bookings, auth, admin, landlord, public, managers


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
    tags=["landlord"]
)

# Include public endpoints (public access)
api_v1_router.include_router(
    public.router,
    tags=["public"]
)

# Include manager endpoints (agency access)
api_v1_router.include_router(
    managers.router,
    prefix="/agency",
    tags=["managers"],
    dependencies=[Depends(role_required("agency"))]
) 