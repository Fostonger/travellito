"""Manager schemas for request/response models."""

from __future__ import annotations

from pydantic import BaseModel


class ManagerIn(BaseModel):
    email: str
    password: str
    first: str | None = None
    last: str | None = None


class ManagerOut(BaseModel):
    id: int
    email: str
    first: str | None = None
    last: str | None = None

    model_config = {"from_attributes": True} 