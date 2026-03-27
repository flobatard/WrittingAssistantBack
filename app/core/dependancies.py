from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user_sub, resolve_user_id
from app.core.database import get_db
    
from app.models.book import Book


@dataclass
class ChatConfig:
    provider: str
    api_key: str | None
    url: str | None
    model: str | None
    provider_type: str

@dataclass
class EmbeddingConfig:
    provider: str
    api_key: str | None
    url: str | None
    model: str | None
    provider_type: str

async def get_chat_config(
    x_chat_provider: str | None = Header(default=None),
    x_chat_provider_type: str | None = Header(default=None),
    x_chat_api_key: str | None = Header(default=None),
    x_chat_api_url: str | None = Header(default=None),
    x_chat_model: str | None = Header(default=None),
) -> ChatConfig:
    if not x_chat_provider:
        raise HTTPException(status_code=401, detail="X-Chat-Provider manquant dans les headers")
    return ChatConfig(
        provider=x_chat_provider,
        provider_type=x_chat_provider_type,
        api_key=x_chat_api_key,
        url=x_chat_api_url,
        model=x_chat_model,
    )

async def get_book_for_user(
    book_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    user_id = await resolve_user_id(sub, db)
    if book.user_id is not None and book.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return book


async def get_embedding_config(
    x_embedding_provider: str | None = Header(default=None),
    x_embedding_provider_type: str | None = Header(default=None),
    x_embedding_api_key: str | None = Header(default=None),
    x_embedding_api_url: str | None = Header(default=None),
    x_embedding_model: str | None = Header(default=None),
) -> EmbeddingConfig:
    if not x_embedding_provider:
        raise HTTPException(status_code=401, detail="X-Embedding-Provider manquant dans les headers")
    return EmbeddingConfig(
        provider=x_embedding_provider,
        provider_type=x_embedding_provider_type,
        api_key=x_embedding_api_key,
        url=x_embedding_api_url,
        model=x_embedding_model,
    )