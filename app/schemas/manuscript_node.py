from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ManuscriptNodeCreate(BaseModel):
    parent_id: Optional[int] = None
    node_type: str = "chapter"
    title: str
    content: Optional[str] = None
    position: float
    is_numbered: bool = True
    depth_level: int = 0


class ManuscriptNodeUpdate(BaseModel):
    parent_id: Optional[int] = None
    node_type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    position: Optional[float] = None
    is_numbered: Optional[bool] = None
    depth_level: Optional[int] = None


class ManuscriptNodeRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    book_id: int
    parent_id: Optional[int]
    node_type: str
    title: str
    content: Optional[str]
    position: float
    is_numbered: bool
    depth_level: int
    created_at: datetime
    updated_at: datetime
