from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.asset import AssetType


class AssetCreate(BaseModel):
    type: AssetType
    name: str
    aliases: list[str] = []
    short_description: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class AssetUpdate(BaseModel):
    type: Optional[AssetType] = None
    name: Optional[str] = None
    # None means "not provided" (field unchanged); [] means "clear aliases"
    aliases: Optional[list[str]] = None
    short_description: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class AssetRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    book_id: int
    type: AssetType
    name: str
    aliases: list[str]
    short_description: Optional[str]
    attributes: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
