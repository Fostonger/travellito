from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from ..deps import SessionDep
from ..models import Apartment, Landlord, Purchase, Tour, LandlordCommission
from ..security import current_user, role_required
from fastapi.responses import Response
import io, csv, qrcode
from qrcode.image.pil import PilImage
from reportlab.pdfgen import canvas as _canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import os

router = APIRouter(
    prefix="/landlord",
    tags=["landlord"],
    dependencies=[Depends(role_required("landlord"))],
)

# ---------------------------------------------------------------------------
#  Schemas
# ---------------------------------------------------------------------------


class ApartmentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    city: str | None = Field(None, max_length=64)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)


class ApartmentOut(ApartmentIn):
    id: int

    model_config = {"from_attributes": True}


class CommissionBody(BaseModel):
    commission_pct: Decimal = Field(..., ge=0, le=100)

    model_config = {
        "json_schema_extra": {
            "example": {"commission_pct": "7.5"},
        },
    }


class EarningsOut(BaseModel):
    total_tickets: int
    tickets_last_30d: int
    total_earnings: Decimal
    earnings_last_30d: Decimal


# Response schema for listing commissions
class CommissionOut(BaseModel):
    tour_id: int
    tour_title: str
    commission_pct: Decimal

    model_config = {"from_attributes": True}


# ----------------------------- NEW SCHEMAS ---------------------------------
class TourForLandlord(BaseModel):
    id: int
    title: str
    price: Decimal
    max_commission_pct: Decimal
    commission_pct: Decimal | None = None


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _get_landlord_id(user: dict) -> int:
    try:
        return int(user["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid landlord token")


# ---------------------------------------------------------------------------
#  Endpoints
# ---------------------------------------------------------------------------


@router.get("/apartments", response_model=List[ApartmentOut])
async def list_apartments(
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    sess: SessionDep = Depends(),
    user=Depends(current_user),
):
    landlord_id = _get_landlord_id(user)

    stmt = (
        select(Apartment)
        .where(Apartment.landlord_id == landlord_id)
        .order_by(Apartment.id)
        .limit(limit)
        .offset(offset)
    )
    apartments = (await sess.scalars(stmt)).all()
    return [ApartmentOut.from_orm(a) for a in apartments]


@router.post("/apartments", response_model=ApartmentOut, status_code=status.HTTP_201_CREATED)
async def create_apartment(payload: ApartmentIn, sess: SessionDep, user=Depends(current_user)):
    landlord_id = _get_landlord_id(user)

    apt = Apartment(landlord_id=landlord_id, **payload.model_dump())
    sess.add(apt)
    await sess.flush()
    await sess.commit()

    return ApartmentOut.from_orm(apt)


@router.patch("/apartments/{apt_id}", response_model=ApartmentOut)
async def update_apartment(
    apt_id: int = Path(..., gt=0),
    payload: ApartmentIn | dict | None = None,
    sess: SessionDep = Depends(),
    user=Depends(current_user),
):
    if payload is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    landlord_id = _get_landlord_id(user)
    apt: Apartment | None = await sess.get(Apartment, apt_id)
    if not apt or apt.landlord_id != landlord_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Apartment not found")

    data = payload if isinstance(payload, dict) else payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(apt, field, value)

    await sess.commit()
    return ApartmentOut.from_orm(apt)


@router.patch("/tours/{tour_id}/commission", response_model=CommissionBody)
async def set_tour_commission(
    tour_id: int = Path(..., gt=0),
    body: CommissionBody | None = None,
    sess: SessionDep = Depends(),
    user=Depends(current_user),
):
    """Set chosen commission (%) for a given tour.

    – Must not exceed tour.max_commission_pct.
    – Upserts LandlordCommission row.
    """
    if body is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Empty payload")

    landlord_id = _get_landlord_id(user)

    tour: Tour | None = await sess.get(Tour, tour_id)
    if not tour:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tour not found")

    if body.commission_pct > tour.max_commission_pct:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Commission cannot exceed tour's max of {tour.max_commission_pct}",
        )

    # Upsert commission row
    stmt = select(LandlordCommission).where(
        LandlordCommission.landlord_id == landlord_id,
        LandlordCommission.tour_id == tour_id,
    )
    lc: LandlordCommission | None = await sess.scalar(stmt)
    if lc is None:
        lc = LandlordCommission(
            landlord_id=landlord_id,
            tour_id=tour_id,
            commission_pct=body.commission_pct,
        )
        sess.add(lc)
    else:
        lc.commission_pct = body.commission_pct

    await sess.commit()

    return CommissionBody(commission_pct=lc.commission_pct)


@router.get("/earnings", response_model=EarningsOut)
async def earnings(period: str = "30d", sess: SessionDep = Depends(), user=Depends(current_user)):
    """Return total tickets and earnings. *period* can be `all` or like `30d`."""

    landlord_id = _get_landlord_id(user)

    # Parse period parameter
    if period == "all":
        cutoff = None
    else:
        try:
            if period.endswith("d"):
                days = int(period[:-1])
                cutoff = datetime.utcnow() - timedelta(days=days)
            else:
                raise ValueError
        except ValueError:  # pragma: no cover
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid period value")

    # Aggregate totals and earnings using commission stored per purchase
    stmt_base = select(
        func.coalesce(func.sum(Purchase.qty), 0).label("tickets"),
        func.coalesce(func.sum(Purchase.amount_gross * (Purchase.commission_pct / Decimal("100"))), 0).label("earnings"),
    ).where(Purchase.landlord_id == landlord_id)

    result_all = await sess.execute(stmt_base)
    tickets_all, earnings_all = result_all.one()

    tickets_all = int(tickets_all or 0)
    earnings_all = Decimal(earnings_all or 0)

    if cutoff:
        stmt_30 = stmt_base.where(Purchase.ts >= cutoff)
        result_30 = await sess.execute(stmt_30)
        tickets_30, earnings_30 = result_30.one()
        tickets_30 = int(tickets_30 or 0)
        earnings_30 = Decimal(earnings_30 or 0)
    else:
        tickets_30 = tickets_all
        earnings_30 = earnings_all

    return EarningsOut(
        total_tickets=tickets_all,
        tickets_last_30d=tickets_30,
        total_earnings=earnings_all.quantize(Decimal("0.01")),
        earnings_last_30d=earnings_30.quantize(Decimal("0.01")),
    )


# ---------------------------------------------------------------------------
#  List all commission settings
# ---------------------------------------------------------------------------


@router.get("/commissions", response_model=List[CommissionOut])
async def list_commissions(
    limit: int = Query(50, gt=0, le=100),
    offset: int = Query(0, ge=0),
    sess: SessionDep = Depends(),
    user=Depends(current_user),
):
    """Return every (tour, commission_pct) set by the landlord."""

    landlord_id = _get_landlord_id(user)

    stmt = (
        select(LandlordCommission, Tour.title)
        .join(Tour, LandlordCommission.tour_id == Tour.id)
        .where(LandlordCommission.landlord_id == landlord_id)
        .order_by(Tour.title)
        .limit(limit)
        .offset(offset)
    )

    rows = (await sess.execute(stmt)).all()

    out: List[CommissionOut] = []
    for lc, title in rows:
        out.append(CommissionOut(tour_id=lc.tour_id, tour_title=title, commission_pct=lc.commission_pct))

    return out


# ----------------------------- NEW ENDPOINTS -------------------------------

@router.get("/tours", response_model=List[TourForLandlord])
async def list_tours_for_commission(
    limit: int = Query(100, gt=0, le=200),
    offset: int = Query(0, ge=0),
    sess: SessionDep = Depends(),
    user=Depends(current_user),
):
    """Return *all* tours together with already-chosen commission (if any).

    Used by the landlord dashboard slider UI so they can pick or adjust their
    commission for every tour, not just the ones previously configured.
    """
    landlord_id = _get_landlord_id(user)

    stmt = (
        select(
            Tour.id,
            Tour.title,
            Tour.price,
            Tour.max_commission_pct,
            LandlordCommission.commission_pct,
        )
        .outerjoin(
            LandlordCommission,
            (LandlordCommission.tour_id == Tour.id)
            & (LandlordCommission.landlord_id == landlord_id),
        )
        .order_by(Tour.title)
        .limit(limit)
        .offset(offset)
    )
    rows = await sess.execute(stmt)

    out: List[TourForLandlord] = []
    for tid, title, price, maxc, chosen in rows:
        out.append(
            TourForLandlord(
                id=tid,
                title=title,
                price=price,
                max_commission_pct=maxc,
                commission_pct=chosen,
            )
        )
    return out

# ---------------------------------------------------------------------------
#  QR-codes bundle as PDF
# ---------------------------------------------------------------------------

@router.get("/apartments/qr-pdf", response_class=Response,
            summary="Download a single PDF containing one QR code per apartment")
async def apartments_qr_pdf(sess: SessionDep = Depends(), user=Depends(current_user)):
    landlord_id = _get_landlord_id(user)

    stmt = select(Apartment).where(Apartment.landlord_id == landlord_id).order_by(Apartment.id)
    apartments = (await sess.scalars(stmt)).all()

    if not apartments:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No apartments found")

    buf = io.BytesIO()
    pdf = _canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    x, y = 50, page_h - 250  # initial cursor

    for apt in apartments:
        payload = f"apt_{apt.id}_{apt.city}_{landlord_id}"
        url = f"https://t.me/{os.getenv('BOT_ALIAS')}?start={payload}"
        qr_img = qrcode.make(url, image_factory=PilImage)
        img_buf = io.BytesIO()
        qr_img.save(img_buf, format="PNG")
        img_buf.seek(0)

        pdf.drawImage(ImageReader(img_buf), x, y, width=200, height=200)
        label = f"Apartment #{apt.id}" + (f" – {apt.name}" if apt.name else "")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(x, y - 15, label)

        # advance cursor – 2 QR codes per row, 3 rows per page
        if x == 50:
            x = 300
        else:
            x = 50
            y -= 250
            if y < 100:
                pdf.showPage()
                y = page_h - 250

    pdf.save()
    buf.seek(0)
    headers = {"Content-Disposition": "attachment; filename=qrcodes.pdf"}
    return Response(content=buf.getvalue(), media_type="application/pdf", headers=headers)

# ---------------------------------------------------------------------------
#  Earnings CSV export (last 30 days)
# ---------------------------------------------------------------------------

@router.get("/earnings.csv", summary="Download detailed last-30-days earnings as CSV")
async def earnings_csv(
    sess: SessionDep = Depends(),
    user=Depends(current_user),
):
    landlord_id = _get_landlord_id(user)
    cutoff = datetime.utcnow() - timedelta(days=30)

    stmt = (
        select(Purchase.ts, Purchase.qty, Purchase.amount, Purchase.commission_pct)
        .where(Purchase.landlord_id == landlord_id, Purchase.ts >= cutoff)
        .order_by(Purchase.ts.desc())
    )
    rows = await sess.execute(stmt)

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerow(["timestamp", "tickets", "amount_net", "commission_pct"])
    for ts, qty, amount, comm in rows:
        writer.writerow([ts.isoformat(), qty, str(amount), str(comm or 0)])

    csv_bytes = csv_buf.getvalue().encode()
    headers = {
        "Content-Type": "text/csv",
        "Content-Disposition": "attachment; filename=earnings_last_30d.csv",
    }
    return Response(content=csv_bytes, headers=headers) 