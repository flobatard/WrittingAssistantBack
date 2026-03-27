from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ManuscriptNodeCreate(BaseModel):
    front_id: Optional[UUID] = None
    parent_front_id: Optional[UUID] = None
    node_type: str = "chapter"
    title: str
    content: Optional[str] = None
    position: float
    is_numbered: bool = True
    depth_level: int = 0


class ManuscriptNodeUpdate(BaseModel):
    front_id: Optional[UUID] = None
    parent_front_id: Optional[UUID] = None
    node_type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    position: Optional[float] = None
    is_numbered: Optional[bool] = None
    depth_level: Optional[int] = None


class ManuscriptNodeRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    front_id: UUID
    book_id: int
    parent_front_id: Optional[UUID]
    node_type: str
    title: str
    content: Optional[str]
    position: float
    is_numbered: bool
    depth_level: int
    created_at: datetime
    updated_at: datetime


class NodeCreateItem(BaseModel):
    line_number: int
    payload: ManuscriptNodeCreate


class NodeUpdateItem(BaseModel):
    front_id: UUID
    payload: ManuscriptNodeUpdate


class NodeDiff(BaseModel):
    to_create: list[NodeCreateItem] = []
    to_update: list[NodeUpdateItem] = []
    to_delete: list[UUID] = []
