from fastapi import File, UploadFile, BackgroundTasks, Depends, FastAPI, Request, HTTPException, Response, Form, Body
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, PlainTextResponse
import qrcode, io, requests, os, json
from .models import Tour, Agency, TourImage, Base, User, Landlord, Apartment, Purchase, Setting
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from .deps import Session, engine, SessionDep
from qrcode.image.pil import PilImage
from .storage import upload_image, presigned, client, BUCKET
from .security import current_user
from datetime import datetime, timedelta
from .api import api_router
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

templates = Jinja2Templates(directory="templates")

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI()

# Attach rate-limiter to app
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return PlainTextResponse("Too many requests", status_code=429)

# Apply a sensible default limit to all endpoints (can be overridden per-route)
app.middleware("http")(limiter.middleware)

app.include_router(api_router)

# Mount new API routers

# ---- routes -------------------------------------------------------------
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure platform default settings exist
    async with Session() as s, s.begin():
        default_setting = await s.get(Setting, "default_max_commission")
        if default_setting is None:
            s.add(Setting(key="default_max_commission", value=10))

    # Start periodic task to lock departures past free-cancellation cutoff
    async def _cutoff_loop():
        while True:
            async with Session() as sess:
                now = datetime.utcnow()
                # Fetch still-modifiable departures joined with their tours
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
            # Sleep 1 hour before next sweep
            await asyncio.sleep(3600)

    asyncio.create_task(_cutoff_loop())

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html",
            {"request": request, "TELEGRAM_BOT_ALIAS": os.getenv("BOT_ALIAS")})

@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(current_user)])
async def admin_dashboard(request: Request):
    """Render the main admin dashboard (summary metrics)."""
    return templates.TemplateResponse("admin/dashboard.html", {"request": request})

# ---------- Admin HTML pages ----------
@app.get("/admin/tours", response_class=HTMLResponse, dependencies=[Depends(current_user)])
async def admin_tours(request: Request):
    return templates.TemplateResponse("admin/tours.html", {"request": request})

@app.get("/admin/agencies", response_class=HTMLResponse, dependencies=[Depends(current_user)])
async def admin_agencies(request: Request):
    return templates.TemplateResponse("admin/agencies.html", {"request": request})

@app.get("/admin/landlords", response_class=HTMLResponse, dependencies=[Depends(current_user)])
async def admin_landlords(request: Request):
    return templates.TemplateResponse("admin/landlords.html", {"request": request})

@app.get("/admin/settings", response_class=HTMLResponse, dependencies=[Depends(current_user)])
async def admin_settings(request: Request):
    return templates.TemplateResponse("admin/settings.html", {"request": request})

# ---------- Lightweight JSON APIs consumed by the admin UI ----------
@app.get("/admin/metrics", dependencies=[Depends(current_user)])
async def admin_metrics(sess: SessionDep):
    tours = await sess.scalar(select(func.count()).select_from(Tour))
    agencies = await sess.scalar(select(func.count()).select_from(Agency))
    landlords = await sess.scalar(select(func.count()).select_from(Landlord))
    return {"tours": tours or 0, "agencies": agencies or 0, "landlords": landlords or 0}

@app.get("/admin/api/tours", dependencies=[Depends(current_user)])
async def api_list_tours(sess: SessionDep):
    result = await sess.execute(select(Tour.id, Tour.title, Tour.price, Tour.max_commission_pct))
    return [
        {"id": tid, "title": title, "price": str(price), "max_commission": str(maxc)}
        for tid, title, price, maxc in result
    ]

@app.get("/admin/api/agencies", dependencies=[Depends(current_user)])
async def api_agencies(sess: SessionDep):
    result = await sess.execute(select(Agency.id, Agency.name, Agency.api_base))
    return [
        {"id": aid, "name": name, "api_base": api_base}
        for aid, name, api_base in result
    ]

@app.get("/admin/api/landlords", dependencies=[Depends(current_user)])
async def api_landlords(sess: SessionDep):
    result = await sess.execute(select(Landlord.id, Landlord.name))
    return [
        {"id": lid, "name": name}
        for lid, name in result
    ]

# ---------- Simple HTML form to upload a tour ----------
class TourIn(BaseModel):
    agency_id: int
    title: str
    description: str
    price: float
    duration_minutes: int | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None

@app.post("/admin/tours")
async def create_tour(
    data: str = Form(...),
    images: list[UploadFile] = File(default=[]),
    user=Depends(current_user)
):
    """Create a tour from the multipart form payload coming from the admin UI.

    The UI sends a field called `data` that contains JSON-encoded tour information
    (see `templates/tour_form.html`). We parse it, validate with the `TourIn`
    schema and persist the record. Images are stored in S3/MinIO via
    `upload_image`.
    """
    payload = json.loads(data)
    tour_in = TourIn(**payload)

    async with Session() as s, s.begin():
        # Ensure agency exists – create a placeholder if missing so we don't hit a
        # FK violation when admins forget to create agencies first.
        agency = await s.get(Agency, tour_in.agency_id)
        if not agency:
            agency = Agency(id=tour_in.agency_id, name=f"Agency #{tour_in.agency_id}")
            s.add(agency)

        tour = Tour(**tour_in.dict())
        s.add(tour)
        await s.flush()

        for img in images:
            key = upload_image(img)
            s.add(TourImage(tour_id=tour.id, key=key))

    return {"id": tour.id}

# ---------- Background pull from 3rd-party API ----------
async def sync_agency(agency_id: int):
    async with Session() as s:
        agency = await s.get(Agency, agency_id)
        r = requests.get(f"{agency.api_base}/tours").json()   # demo
        for item in r:
            stmt = select(Tour).where(Tour.external_id == item["id"])
            db_tour = await s.scalar(stmt)
            if not db_tour:
                db_tour = Tour(agency_id=agency.id)
            db_tour.title = item["title"]
            db_tour.description = item["description"]
            db_tour.price = item["price"]
            s.add(db_tour)

@app.post("/admin/agency/{aid}/sync")
async def manual_sync(aid: int, bg: BackgroundTasks):
    bg.add_task(sync_agency, aid)
    return {"scheduled": True}

# ----------------------------------------------------------------------
#                       LANDLORD / PARTNER PAGES
# ----------------------------------------------------------------------

# Helper to fetch the landlord linked to the current user (one-to-one for now)

async def current_landlord(sess: SessionDep, user=Depends(current_user)) -> Landlord:
    stmt = select(Landlord).where(Landlord.user_id == user["u"])
    landlord = await sess.scalar(stmt)
    if not landlord:
        raise HTTPException(403, "No landlord account linked to this user")
    return landlord

# ------------------ Dashboard ------------------

@app.get("/partner", response_class=HTMLResponse, dependencies=[Depends(current_user)])
async def landlord_dashboard(request: Request, sess: SessionDep, landlord: Landlord = Depends(current_landlord)):
    # Aggregated metrics
    now = datetime.utcnow()
    last_30 = now - timedelta(days=30)

    # All-time metrics
    res_all = await sess.execute(
        # Sum gross commission earnings instead of tourist net price
        select(
            func.coalesce(func.sum(Purchase.qty), 0),
            func.coalesce(
                func.sum(Purchase.amount_gross * (func.coalesce(Purchase.commission_pct, 0) / 100)),
                0,
            ),
        )
        .where(Purchase.landlord_id == landlord.id)
    )
    total_qty, total_amount = res_all.one()

    # Last-30-days metrics
    res_30 = await sess.execute(
        select(
            func.coalesce(func.sum(Purchase.qty), 0),
            func.coalesce(
                func.sum(Purchase.amount_gross * (func.coalesce(Purchase.commission_pct, 0) / 100)),
                0,
            ),
        )
        .where(Purchase.landlord_id == landlord.id, Purchase.ts >= last_30)
    )
    last_qty, last_amount = res_30.one()

    # Apartments list
    apts_stmt = select(Apartment).where(Apartment.landlord_id == landlord.id)
    apartments = (await sess.scalars(apts_stmt)).all()

    return templates.TemplateResponse("landlord_dashboard.html", {
        "request": request,
        "landlord": landlord,
        "total_qty": total_qty,
        "total_amount": total_amount,
        "last_qty": last_qty,
        "last_amount": last_amount,
        "apartments": apartments,
    })

# ------------------ Apartment Form ------------------

@app.get("/partner/apartments/new", response_class=HTMLResponse, dependencies=[Depends(current_user)])
async def new_apartment_form(request: Request):
    return templates.TemplateResponse("apartment_form.html", {"request": request})


class ApartmentIn(BaseModel):
    name: str | None = None
    city: str


@app.post("/partner/apartments")
async def create_apartment(data: ApartmentIn, sess: SessionDep, landlord: Landlord = Depends(current_landlord)):
    apt = Apartment(
        landlord_id=landlord.id,
        name=data.name,
        city=data.city,
    )
    sess.add(apt)
    await sess.commit()
    await sess.refresh(apt)
    return {"id": apt.id}


# ------------------ QR code per apartment ------------------
# Example payload: apt_<id>_<city>_<ref>

@app.get("/partner/apartments/{apt_id}/qrcode", response_class=Response, dependencies=[Depends(current_user)])
async def apartment_qr(apt_id: int, landlord: Landlord = Depends(current_landlord), sess: SessionDep):
    apt = await sess.get(Apartment, apt_id)
    if not apt or apt.landlord_id != landlord.id:
        raise HTTPException(404)

    ref = landlord.referral_code or str(landlord.id)
    payload = f"apt_{apt.id}_{apt.city}_{ref}"
    url = f"https://t.me/{os.getenv('BOT_ALIAS')}?start={payload}"

    img = qrcode.make(url, image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")

# ----------------- Platform settings (DB-backed) -----------------

@app.get("/admin/api/settings", dependencies=[Depends(current_user)])
async def get_settings(sess: SessionDep):
    rows = (await sess.scalars(select(Setting))).all()
    return {row.key: row.value for row in rows}

class SettingBody(BaseModel):
    key: str
    value: float | int | str | bool

@app.post("/admin/api/settings", dependencies=[Depends(current_user)])
async def update_settings(data: SettingBody, sess: SessionDep):
    async with sess.begin():
        setting: Setting | None = await sess.get(Setting, data.key)
        if setting is None:
            setting = Setting(key=data.key, value=data.value)
            sess.add(setting)
        else:
            setting.value = data.value
    return {"ok": True}

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

# ----------------------------------------------------------------------
#                           HEALTH CHECK
# ----------------------------------------------------------------------

@app.get("/healthz")
async def healthz(sess: SessionDep):
    """Return simple JSON telling if DB and S3 are reachable.

    Format: {"db": "ok"|"error", "s3": "ok"|"error"}
    """
    status = {"db": "ok", "s3": "ok"}

    # --- DB ------------------------------------------------------------
    try:
        await sess.scalar(select(1))
    except Exception as exc:  # pragma: no cover – surface error downstream
        status["db"] = "error"

    # --- S3 ------------------------------------------------------------
    try:
        # lightweight call; returns bool or raises
        client.bucket_exists(BUCKET)
    except Exception:
        status["s3"] = "error"

    return status