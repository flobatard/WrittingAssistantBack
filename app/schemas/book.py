from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BookCreate(BaseModel):
    title: str
    genre: Optional[str]
    content: str


class BookUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    content: Optional[str] = None


class BookRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    content: str
    genre: Optional[str]
    embedding_model_used: Optional[str]
    created_at: datetime
    updated_at: datetime


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
