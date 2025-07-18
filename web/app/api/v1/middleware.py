from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import BaseError


async def exception_handler(request: Request, call_next):
    """Global exception handler middleware"""
    try:
        return await call_next(request)
    except BaseError as exc:
        # Handle our custom exceptions
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "details": exc.details
            }
        )
    except Exception as exc:
        # Handle unexpected exceptions
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "details": {}
            }
        )


async def get_landlord_for_templates(request: Request, sess, user):
    """Get landlord data for templates.
    
    This function is used to retrieve landlord data to pass to templates for notification display.
    """
    # Only proceed if user is a landlord
    if not user or user.get("role") != "landlord":
        return None
        
    try:
        # Import here to avoid circular imports
        from app.services.landlord_service import LandlordService
        
        service = LandlordService(sess)
        landlord = await service.get_landlord_by_user_id(int(user["sub"]))
        return landlord
    except Exception:
        # If there's any error, return None to avoid breaking templates
        return None


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler for request validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "details": {"errors": errors}
        }
    ) 