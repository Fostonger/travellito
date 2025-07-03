from fastapi import APIRouter, Depends

from app.security import role_required
from app.api.v1.endpoints import tours


# Create main API router
api_v1_router = APIRouter()

# Include tour endpoints (agency access)
api_v1_router.include_router(
    tours.router,
    prefix="/agency/tours",
    tags=["tours"],
    dependencies=[Depends(role_required("agency"))]
)

# TODO: Add more endpoint routers as they are refactored
# api_v1_router.include_router(departures.router, prefix="/agency/departures", tags=["departures"])
# api_v1_router.include_router(bookings.router, prefix="/agency/bookings", tags=["bookings"])
# api_v1_router.include_router(admin.router, prefix="/admin", tags=["admin"]) 