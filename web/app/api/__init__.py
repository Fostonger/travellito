from fastapi import APIRouter

from .public import router as public_router
from .auth import router as auth_router

# Placeholder imports for future modules so that include_router doesn't fail even
# if the module is still empty.
try:
    from .bookings import router as bookings_router
except ImportError:
    bookings_router = APIRouter()
try:
    from .broadcast import router as broadcast_router
except ImportError:
    broadcast_router = APIRouter()
try:
    from .agency import router as agency_router
except ImportError:
    agency_router = APIRouter()
try:
    from .landlord import router as landlord_router
except ImportError:
    landlord_router = APIRouter()
try:
    from .admin import router as admin_router
except ImportError:
    admin_router = APIRouter()
try:
    from .referral import router as referral_router
except ImportError:
    referral_router = APIRouter()
try:
    from .external import router as external_router
except ImportError:
    external_router = APIRouter()


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(public_router, tags=["public"])
api_router.include_router(bookings_router, tags=["bookings"])
api_router.include_router(broadcast_router, tags=["broadcast"])
api_router.include_router(agency_router, tags=["agency"])
api_router.include_router(landlord_router, tags=["landlord"])
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(referral_router, tags=["referrals"])
api_router.include_router(external_router, tags=["external"]) 