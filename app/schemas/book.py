from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BookCreate(BaseModel):
    title: str
    content: str


class BookUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class BookRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    content: str
    embedding_model_used: Optional[str]
    created_at: datetime
    updated_at: datetime
