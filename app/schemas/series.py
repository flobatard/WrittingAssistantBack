from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SeriesCreate(BaseModel):
    title: str
    description: Optional[str] = None


class SeriesUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class SeriesRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: Optional[int]
    title: str
    description: Optional[str]
    created_at: datetime
