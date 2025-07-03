"""Broadcast schemas for request/response models."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class BroadcastBody(BaseModel):
    text: str | None = Field(None, max_length=4096)
    photo_url: str | None = None
    document_url: str | None = None

    model_config = {
        "extra": "forbid",
    }


class BroadcastResponse(BaseModel):
    scheduled: bool


class DepartureOut(BaseModel):
    id: int
    tour_title: str
    starts_at: datetime

    model_config = {
        "from_attributes": True,
    } 