import time
from jose import jwt
from fastapi import File, UploadFile, BackgroundTasks, Depends, FastAPI, Request, HTTPException, Response, Form
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import qrcode, io, requests, os, json
from aiogram.utils.auth_widget import check_integrity
from .api_buy import router as buy_router
from .models import Tour, Agency, TourImage, Base, User
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from .deps import Session, engine, SessionDep
from qrcode.image.pil import PilImage
from .storage import upload_image
from .storage import presigned

TOKEN     = os.getenv("BOT_TOKEN")
SECRET    = os.getenv("SECRET_KEY") # random 32 bytes
templates = Jinja2Templates(directory="templates")

app = FastAPI()

# ---- helpers ------------------------------------------------------------
def sign(payload: dict) -> str:
    return jwt.encode(payload, SECRET, algorithm="HS256")

async def current_user(req: Request):
    token = req.cookies.get("session")
    if not token:
        raise HTTPException(401)
    return jwt.decode(token, SECRET, algorithms=["HS256"])

app.include_router(buy_router)

# ---- routes -------------------------------------------------------------
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html",
            {"request": request, "TELEGRAM_BOT_ALIAS": os.getenv("BOT_ALIAS")})

@app.get("/admin/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("tour_form.html", {"request": request})

@app.get("/auth/telegram")
async def telegram_auth(request: Request, resp: Response):
    data = dict(request.query_params)
    if not check_integrity(TOKEN, data):
        raise HTTPException(400, "Bad signature")
    async with Session() as s, s.begin():
        user = await User.get_or_create(s, data)   # custom helper
    resp.set_cookie("session", sign({"u": user.id, "exp": time.time()+86400}),
                    httponly=True, secure=True)
    return {"ok": True}

@app.get("/admin", dependencies=[Depends(current_user)])
def admin_home():
    return {"status": "Welcome to the admin panel"}

# ---------- QR code ----------
@app.get("/landlord/{landlord_id}/qrcode", response_class=Response)
async def landlord_qr(landlord_id: int):
    url = f"https://t.me/{os.getenv('BOT_ALIAS')}?start=ref_{landlord_id}"
    img = qrcode.make(url, image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(),
                    media_type="image/png")

# ---------- Simple HTML form to upload a tour ----------
class TourIn(BaseModel):
    agency_id: int
    title: str
    description: str
    price: float

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

# ---------- Payment webhook ----------
# NOTE: Stripe has been removed from the project. A new payment provider will
# be integrated in the future. Keep this placeholder so that routing does not
# break if referenced elsewhere.
@app.post("/webhook/payment")
async def payment_hook():
    raise HTTPException(501, "Payment integration pending")

@app.get("/tours/{tid}")
async def tour_detail(tid: int, sess: SessionDep):
    """Return full tour data including presigned image URLs.

    Uses `selectinload` to eagerly fetch `tour.images` within the same DB round-trip,
    avoiding the async-unfriendly lazy loading that triggered `MissingGreenlet`.
    """
    stmt = (
        select(Tour)
        .options(selectinload(Tour.images))
        .where(Tour.id == tid)
    )
    tour = await sess.scalar(stmt)
    if not tour:
        raise HTTPException(404, "Tour not found")

    return {
        "id": tour.id,
        "title": tour.title,
        "description": tour.description,
        "price": str(tour.price),
        "images": [presigned(img.key) for img in tour.images],
    }

# ---------- Tours listing for bot ----------
@app.get("/tours")
async def list_tours(sess: SessionDep):
    """Return a lightweight list of tours for the Telegram bot UI."""
    result = await sess.execute(select(Tour.id, Tour.title))
    return [
        {"id": tid, "title": title}
        for tid, title in result
    ]

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")