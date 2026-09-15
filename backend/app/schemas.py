"""Pydantic schemas for requests/responses."""
import uuid

from fastapi_users import schemas
from pydantic import BaseModel, Field


# ── Auth ──
class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: str | None = None
    institution: str | None = None


class UserCreate(schemas.BaseUserCreate):
    display_name: str | None = None
    institution: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None
    institution: str | None = None


# ── Saved searches / favorites ──
class SavedSearchCreate(BaseModel):
    name: str
    params: dict


class SavedSearchRead(BaseModel):
    id: int
    name: str
    params: dict


class FavoriteCreate(BaseModel):
    entity_type: str = Field(pattern="^(researcher|article|topic)$")
    entity_id: int


# ── Tracking ──
class TrackEvent(BaseModel):
    session_id: uuid.UUID
    event_type: str
    payload: dict = Field(default_factory=dict)
