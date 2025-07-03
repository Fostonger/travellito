from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import get_session

# Type alias for dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_session)] 