# web/app/models.py
from sqlalchemy import String, BigInteger, TIMESTAMP, func
from sqlalchemy.orm import mapped_column, DeclarativeBase
from sqlalchemy import select

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id        = mapped_column(BigInteger, primary_key=True)
    tg_id  = mapped_column(BigInteger, unique=True, nullable=False)
    first     = mapped_column(String(64))
    last      = mapped_column(String(64))
    username  = mapped_column(String(64))
    created   = mapped_column(TIMESTAMP, server_default=func.now())

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