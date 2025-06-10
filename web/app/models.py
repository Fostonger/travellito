from sqlalchemy import (
    String, BigInteger, Integer, ForeignKey, Numeric, DateTime,
    func, select
)
from sqlalchemy.orm import mapped_column, relationship, DeclarativeBase

class Base(DeclarativeBase): ...

# ---------- Core actors ----------
class Agency(Base):
    __tablename__ = "agencies"
    id          = mapped_column(Integer, primary_key=True)
    name        = mapped_column(String(120), unique=True, nullable=False)
    api_base    = mapped_column(String(256))        # optional third-party API
    tours       = relationship("Tour", back_populates="agency")

class Landlord(Base):
    __tablename__ = "landlords"
    id        = mapped_column(Integer, primary_key=True)
    name      = mapped_column(String(120))
    qr_sent   = mapped_column(DateTime)

class User(Base):
    __tablename__ = "users"
    id        = mapped_column(Integer, primary_key=True)
    tg_id     = mapped_column(BigInteger, unique=True, nullable=False)
    first     = mapped_column(String(64))
    last      = mapped_column(String(64))
    username  = mapped_column(String(64))
    created   = mapped_column(DateTime, server_default=func.now())

    @classmethod
    async def get_or_create(cls, session, tg):
        tg_id = int(tg["id"])
        stmt = select(cls).where(cls.tg_id == tg_id)  # keep SQLAlchemy-2.0 form
        result = await session.scalar(stmt)  # scalar() returns or None
        if result:
            return result
        user = cls(
            tg_id=tg_id,
            first=tg.get("first_name"),
            last=tg.get("last_name"),
            username=tg.get("username"),
        )
        session.add(user)
        return user

# ---------- Tours ----------
class Tour(Base):
    __tablename__ = "tours"
    id          = mapped_column(Integer, primary_key=True)
    agency_id   = mapped_column(ForeignKey("agencies.id"))
    title       = mapped_column(String(200))
    description = mapped_column(String(2000))
    price       = mapped_column(Numeric(10, 2))
    agency      = relationship("Agency", back_populates="tours")
    images      = relationship("TourImage", back_populates="tour")

class TourImage(Base):
    __tablename__ = "tour_images"
    id       = mapped_column(Integer, primary_key=True)
    tour_id  = mapped_column(ForeignKey("tours.id"))
    key      = mapped_column(String(256))
    tour     = relationship("Tour", back_populates="images")

# ---------- Referrals & Purchases ----------
class Referral(Base):
    __tablename__ = "referrals"
    user_id      = mapped_column(ForeignKey("users.id"), primary_key=True)
    landlord_id  = mapped_column(ForeignKey("landlords.id"), primary_key=True)
    ts           = mapped_column(DateTime, server_default=func.now())

class Purchase(Base):
    __tablename__ = "purchases"
    id         = mapped_column(Integer, primary_key=True)
    user_id    = mapped_column(ForeignKey("users.id"))
    tour_id    = mapped_column(ForeignKey("tours.id"))
    landlord_id = mapped_column(ForeignKey("landlords.id"))
    qty        = mapped_column(Integer, default=1)
    amount     = mapped_column(Numeric(10, 2))
    ts         = mapped_column(DateTime, server_default=func.now())