import os
from typing import AsyncGenerator, Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DB_DSN    = os.getenv("DB_DSN")     # postgresql+asyncpg://user:pass@db/app
engine = create_async_engine(DB_DSN, echo=False, pool_size=5)
Session = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with Session() as s:                  # open connection
        yield s                                 # provide it to the handler
        # session closes automatically afterwards

SessionDep = Annotated[AsyncSession, Depends(get_session)]