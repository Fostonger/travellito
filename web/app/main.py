import os, hmac, time, secrets
from jose import jwt
from fastapi import FastAPI, Request, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from aiogram.utils.auth_widget import check_integrity
from .models import Base, User       # see next section

TOKEN     = os.getenv("BOT_TOKEN")
DB_DSN    = os.getenv("DB_DSN")     # postgresql+asyncpg://user:pass@db/app
SECRET    = os.getenv("SECRET_KEY") # random 32 bytes
templates = Jinja2Templates(directory="templates")

app = FastAPI()
engine = create_async_engine(DB_DSN, echo=False, pool_size=5)
Session = async_sessionmaker(engine, expire_on_commit=False)

# ---- helpers ------------------------------------------------------------
def sign(payload: dict) -> str:
    return jwt.encode(payload, SECRET, algorithm="HS256")

async def current_user(req: Request):
    token = req.cookies.get("session")
    if not token:
        raise HTTPException(401)
    return jwt.decode(token, SECRET, algorithms=["HS256"])

# ---- routes -------------------------------------------------------------
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html",
            {"request": request, "TELEGRAM_BOT_ALIAS": os.getenv("BOT_ALIAS")})

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