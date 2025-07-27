from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from jose import JWTError
import time

from app.core import BaseError
from app.security import decode_token, ACCESS_TOKEN_EXP_SECONDS, REFRESH_TOKEN_EXP_SECONDS, _extract_token, _extract_refresh_token, mint_tokens


class TokenRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically refresh expired access tokens"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip token refresh for auth endpoints to avoid loops
        if request.url.path.startswith("/api/v1/auth/"):
            return await call_next(request)
            
        # Extract tokens
        access_token = await _extract_token(request)
        refresh_token = await _extract_refresh_token(request)
        
        # If no tokens, continue with request (will be handled by auth dependencies)
        if not refresh_token:
            return await call_next(request)
        
        # Try the original request first
        response = None
        token_refreshed = False
        
        try:
            # Continue with the original request
            response = await call_next(request)
            
            # If we got a 401, it might be due to an expired token
            if response.status_code == 401:
                # Get database session
                from app.deps import get_session
                from app.services.auth_service import AuthService
                
                # Create a new session for this middleware
                async for session in get_session():
                    try:
                        # Create auth service
                        service = AuthService(session)
                        
                        # Refresh the token
                        new_access_token = await service.refresh_access_token(refresh_token)
                        token_refreshed = True
                        
                        # Create a new request with the new token
                        # We need to re-execute the original request with the new token
                        # Clone the original request
                        new_request = Request(request.scope, request.receive)
                        
                        # Add the new token to the request state for the current_user dependency
                        new_request.state.access_token = new_access_token
                        
                        # Re-execute the request
                        response = await call_next(new_request)
                        
                        # Set the new access token cookie
                        response.set_cookie(
                            key="access_token",
                            value=new_access_token,
                            httponly=True,
                            secure=True,
                            samesite="lax",
                            max_age=ACCESS_TOKEN_EXP_SECONDS
                        )
                        
                        break
                    except Exception as e:
                        print(f"Token refresh error: {e}")
                        # If refresh fails, continue with the original 401 response
                        pass
        except Exception as e:
            # If there's an error, just continue with the original request
            print(f"Middleware error: {e}")
            if not response:
                response = await call_next(request)
        
        return response


class ClientIDMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and manage Yandex Metrica client IDs"""
    
    async def dispatch(self, request: Request, call_next):
        # Extract client ID from headers or cookies
        client_id = request.headers.get("X-Client-Id") or request.cookies.get("_ym_uid")
        
        # If not found, generate a new one
        if not client_id:
            client_id = str(uuid.uuid4())
        
        # Store in request state for use in route handlers
        request.state.client_id = client_id
        
        # Process the request
        response = await call_next(request)
        
        # Set the client ID cookie in the response if it wasn't in cookies
        if not request.cookies.get("_ym_uid"):
            response.set_cookie(
                "_ym_uid", 
                client_id, 
                max_age=31536000,  # 1 year
                httponly=False,    # Allow JS to access for Metrica
                samesite="lax"
            )
        
        return response


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