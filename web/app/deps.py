from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import get_session

import os

# Type alias for dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_session)] 
DB_DSN = os.getenv("DB_DSN")