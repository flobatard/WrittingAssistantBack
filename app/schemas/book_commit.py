from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CommitCreate(BaseModel):
    message: Optional[str] = None


class CommitRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    book_id: int
    message: Optional[str]
    created_at: datetime
    snapshot_count: int


class ManuscriptNodeSnapshotRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    commit_id: int
    front_id: UUID
    parent_front_id: Optional[UUID]
    node_type: str
    title: str
    content: Optional[str]
    position: float
    is_numbered: bool
    depth_level: int


