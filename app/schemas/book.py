from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.manuscript_node import ManuscriptNodeRead


class BookCreate(BaseModel):
    title: str
    genre: Optional[str] = None
    series_id: Optional[int] = None
    parent_book_id: Optional[int] = None
    position_in_series: Optional[float] = None
    is_spinoff: bool = False


class BookUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    series_id: Optional[int] = None
    parent_book_id: Optional[int] = None
    position_in_series: Optional[float] = None
    is_spinoff: Optional[bool] = None


class IaSettingsUpdate(BaseModel):
    ia_settings: dict


class BookRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: Optional[int]
    series_id: Optional[int]
    parent_book_id: Optional[int]
    position_in_series: Optional[float]
    is_spinoff: bool
    title: str
    genre: Optional[str]
    ia_settings: Optional[dict]
    embedding_model_used: Optional[str]
    last_vectorized_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    manuscript_nodes: list[ManuscriptNodeRead]


class ChatRequest(BaseModel):
    question: str
    k: int = 5
    stream: bool = False


class ChatSource(BaseModel):
    content: str
    score: float
    chunk_index: int


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[ChatSource]
