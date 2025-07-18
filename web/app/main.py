"""Main application entry point using clean architecture."""

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
import os
import asyncio
from datetime import datetime, timedelta, date
import httpx
from fastapi.responses import Response
from typing import Optional

from .infrastructure.database import engine, AsyncSessionFactory
from .deps import SessionDep
from .models import Setting, Departure, Tour, Base
from .api.v1.api import api_v1_router
from .api.v1.middleware import exception_handler
from .storage import client, BUCKET
from .security import role_required, current_user

# Rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

templates = Jinja2Templates(directory="templates")
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Ensure platform default settings exist
    async with AsyncSessionFactory() as s:
        default_setting = await s.get(Setting, "default_max_commission")
        if default_setting is None:
            s.add(Setting(key="default_max_commission", value=10))
            await s.commit()
    
    # Start periodic task to lock departures past free-cancellation cutoff
    async def _cutoff_loop():
        while True:
            async with AsyncSessionFactory() as sess:
                now = datetime.utcnow()
                stmt = select(Departure).join(Tour).where(Departure.modifiable == True)
                deps = (await sess.scalars(stmt)).unique().all()
                changed = False
                for dep in deps:
                    cutoff = dep.starts_at - timedelta(hours=dep.tour.free_cancellation_cutoff_h)
                    if now >= cutoff:
                        dep.modifiable = False
                        changed = True
                if changed:
                    await sess.commit()
            await asyncio.sleep(3600)
    
    task = asyncio.create_task(_cutoff_loop())
    
    yield
    
    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# Create FastAPI app
app = FastAPI(
    title="Travellito API",
    description="Tour booking platform API",
    version="2.0.0",
    lifespan=lifespan
)

# Attach rate-limiter
app.state.limiter = limiter

# CORS Configuration
_raw_origins = os.getenv("CORS_ALLOW_ORIGINS") or os.getenv("WEBAPP_URL", "*")

if _raw_origins.strip() == "*":
    _allow_origins = ["*"]
    _allow_credentials = False
else:
    _allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    _allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Rate limiting
@app.exception_handler(RateLimitExceeded)
async def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return PlainTextResponse("Too many requests", status_code=429)

app.add_middleware(SlowAPIMiddleware)

# Exception handling
app.add_exception_handler(Exception, exception_handler)

# Include v1 API with all endpoints
app.include_router(api_v1_router, prefix="/api/v1")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Health check
@app.get("/healthz")
async def healthz(sess: SessionDep):
    """Health check endpoint."""
    status = {"db": "ok", "s3": "ok"}
    
    try:
        await sess.scalar(select(1))
    except Exception:
        status["db"] = "error"
    
    try:
        client.bucket_exists(BUCKET)
    except Exception:
        status["s3"] = "error"
    
    return status

# Root endpoint
@app.get("/")
async def root():
    """API root."""
    return {
        "message": "Welcome to Travellito API v2.0",
        "docs": "/docs",
        "health": "/healthz"
    }

# Legacy HTML pages (temporary for backward compatibility)
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "TELEGRAM_BOT_ALIAS": os.getenv("BOT_ALIAS")
    })

# Admin pages
@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(role_required("admin"))])
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})

@app.get("/admin/tours", response_class=HTMLResponse, dependencies=[Depends(role_required("admin"))])
async def admin_tours(request: Request):
    return templates.TemplateResponse("admin/tours.html", {"request": request})

@app.get("/admin/agencies", response_class=HTMLResponse, dependencies=[Depends(role_required("admin"))])
async def admin_agencies(request: Request):
    return templates.TemplateResponse("admin/agencies.html", {"request": request})

@app.get("/admin/landlords", response_class=HTMLResponse, dependencies=[Depends(role_required("admin"))])
async def admin_landlords(request: Request):
    return templates.TemplateResponse("admin/landlords.html", {"request": request})

@app.get("/admin/settings", response_class=HTMLResponse, dependencies=[Depends(role_required("admin"))])
async def admin_settings(request: Request):
    return templates.TemplateResponse("admin/settings.html", {"request": request})

# Partner pages
@app.get("/api/v1/landlord", response_class=HTMLResponse, dependencies=[Depends(role_required("landlord"))])
async def landlord_dashboard(request: Request, sess: SessionDep, user=Depends(current_user)):
    """Landlord dashboard page."""
    from app.services.landlord_service import LandlordService
    from app.core.exceptions import NotFoundError
    
    # Get landlord data via service (following clean architecture)
    try:
        service = LandlordService(sess)
        data = await service.get_dashboard_data(int(user["sub"]))
        
        return templates.TemplateResponse("landlord_dashboard.html", {
            "request": request,
            "landlord": data["landlord"],
            "apartments": data["apartments"],
            "total_qty": data["metrics"]["total_qty"],
            "total_amount": data["metrics"]["total_amount"],
            "last_qty": data["metrics"]["last_qty"],
            "last_amount": data["metrics"]["last_amount"]
        })
    except NotFoundError:
        # If landlord not found, render with default values
        return templates.TemplateResponse("landlord_dashboard.html", {
            "request": request,
            "apartments": []
        })

@app.get("/api/v1/landlord/apartments/new", response_class=HTMLResponse, dependencies=[Depends(role_required("landlord"))])
async def new_apartment_form(request: Request):
    return templates.TemplateResponse("apartment_form.html", {"request": request})

@app.get("/signup/landlord", response_class=HTMLResponse)
def landlord_signup_page(request: Request):
    return templates.TemplateResponse("landlord_signup.html", {"request": request})

@app.post("/signup/landlord")
async def landlord_signup_redirect(request: Request):
    """Redirect to the API endpoint for landlord signup."""
    data = await request.json()
    
    # Forward the request to our API endpoint
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{request.base_url}api/v1/public/signup/landlord",
            json=data
        )
        
        return Response(content=response.content, status_code=response.status_code)

# Agency pages
@app.get("/agency", response_class=HTMLResponse, dependencies=[Depends(role_required("agency"))])
async def agency_dashboard(request: Request):
    return templates.TemplateResponse("agency/dashboard.html", {"request": request})

@app.get("/agency/tours", response_class=HTMLResponse, dependencies=[Depends(role_required("agency"))])
async def agency_tours_page(request: Request):
    return templates.TemplateResponse("agency/tours.html", {"request": request})

@app.get("/agency/managers", response_class=HTMLResponse, dependencies=[Depends(role_required("agency"))])
async def agency_managers_page(request: Request):
    return templates.TemplateResponse("agency/managers.html", {"request": request})

@app.get("/agency/bookings", response_class=HTMLResponse, dependencies=[Depends(role_required("agency"))])
async def agency_bookings_page(request: Request):
    return templates.TemplateResponse("agency/bookings.html", {"request": request})

@app.get("/agency/departures", response_class=HTMLResponse, dependencies=[Depends(role_required("agency"))])
async def agency_departures_page(request: Request):
    return templates.TemplateResponse("agency/departures.html", {"request": request})

# Add this route for timezone testing
@app.get("/timezone-test", response_class=HTMLResponse)
async def timezone_test(request: Request):
    return templates.TemplateResponse("timezone_test.html", {"request": request})
