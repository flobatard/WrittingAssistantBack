from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.asset import AssetType


class NodeExport(BaseModel):
    front_id: UUID
    parent_front_id: Optional[UUID] = None
    node_type: str
    title: str
    content: Optional[str] = None
    position: float
    is_numbered: bool
    depth_level: int


class AssetExport(BaseModel):
    type: AssetType
    name: str
    aliases: list[str] = []
    short_description: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class BookExport(BaseModel):
    title: str
    genre: Optional[str] = None
    is_spinoff: bool = False
    ia_settings: Optional[dict] = None
    manuscript_nodes: list[NodeExport] = []
    assets: list[AssetExport] = []
