import time
from jose import jwt
from fastapi import File, UploadFile, BackgroundTasks, Depends, FastAPI, Request, HTTPException, Response
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import qrcode, io, requests, os, stripe
from aiogram.utils.auth_widget import check_integrity
from .api_buy import router as buy_router
from .models import Tour, Agency, Purchase, TourImage, Base, User
from sqlalchemy import select
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

stripe.api_key = os.getenv("STRIPE_SK")            # add to compose

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
    data: TourIn,
    images: list[UploadFile] = File(default=[]),
    user=Depends(current_user)
):
    async with Session() as s, s.begin():
        tour = Tour(**data.dict())
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

# ---------- Stripe webhook ----------
@app.post("/webhook/stripe")
async def stripe_hook(request: Request):
    sig  = request.headers["Stripe-Signature"]
    evt  = stripe.Webhook.construct_event(
        await request.body(),
        sig,
        os.getenv("STRIPE_WH_SEC")
    )
    if evt["type"] == "checkout.session.completed":
        data = evt["data"]["object"]
        user_id     = int(data["client_reference_id"])
        landlord_id = int(data["metadata"]["landlord_id"])
        tour_id     = int(data["metadata"]["tour_id"])
        qty         = int(data["metadata"]["qty"])
        amount      = float(data["amount_total"] / 100)
        async with Session() as s, s.begin():
            s.add(Purchase(user_id=user_id, landlord_id=landlord_id,
                           tour_id=tour_id, qty=qty, amount=amount))
    return {"ok": True}

@app.get("/tours/{tid}")
async def tour_detail(tid: int, sess: SessionDep):
    tour = await sess.get(Tour, tid)
    return {
        "id": tour.id,
        "title": tour.title,
        "description": tour.description,
        "price": str(tour.price),
        "images": [presigned(img.key) for img in tour.images]
    }

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")