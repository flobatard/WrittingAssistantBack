import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user_sub, resolve_user_id
from app.core.database import get_db
from app.core.dependancies import EmbeddingConfig, get_book_for_user, get_embedding_config
from app.core.s3 import delete_objects_by_prefix
from app.models.book import Book
from app.models.manuscript_node import ManuscriptNode
from app.schemas.book import BookCreate, BookRead, BookUpdate, ChatRequest, ChatResponse, IaSettingsUpdate
from app.services.rag import vectorize_book, query_book

logger = logging.getLogger(__name__)

router = APIRouter(tags=["books"])


@router.post("/", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(
    payload: BookCreate,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    book = Book(**payload.model_dump(), user_id=user_id)
    db.add(book)
    await db.flush()

    await db.refresh(book)
    return book


@router.get("/", response_model=list[BookRead])
async def list_books(
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    if user_id is not None:
        result = await db.execute(
            select(Book)
            .where((Book.user_id == None) | (Book.user_id == user_id))
            .order_by(Book.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Book).where(Book.user_id == None).order_by(Book.created_at.desc())
        )
    return result.scalars().all()


@router.get("/{book_id}", response_model=BookRead)
async def get_book(
    book: Book = Depends(get_book_for_user),
):
    return book


@router.put("/{book_id}", response_model=BookRead)
async def update_book(
    payload: BookUpdate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)

    await db.flush()
    await db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        delete_objects_by_prefix(f"books/{book.id}/")
    except Exception:
        logger.warning("Failed to delete S3 folder for book %s", book.id, exc_info=True)
    await db.delete(book)


@router.get("/{book_id}/ia-settings")
async def get_ia_settings(
    book: Book = Depends(get_book_for_user),
):
    return book.ia_settings or {}


@router.put("/{book_id}/ia-settings")
async def update_ia_settings(
    payload: IaSettingsUpdate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    if len(json.dumps(payload.ia_settings.model_dump()).encode()) > 1_000_000:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="ia_settings payload exceeds 1 MB")
    book.ia_settings = payload.ia_settings.model_dump()
    await db.flush()
    await db.refresh(book)
    return book.ia_settings


@router.post("/{book_id}/vectorize")
async def vectorize(
    book: Book = Depends(get_book_for_user),
    embedding_config: EmbeddingConfig = Depends(get_embedding_config),
    db: AsyncSession = Depends(get_db),
):
    nodes_result = await db.execute(
        select(ManuscriptNode)
        .where(ManuscriptNode.book_id == book.id, ManuscriptNode.content.isnot(None))
        .order_by(ManuscriptNode.position)
    )
    chapters = list(nodes_result.scalars().all())

    result = vectorize_book(book, embedding_config, chapters)

    book.embedding_model_used = embedding_config.model
    book.last_vectorized_at = datetime.now(timezone.utc)
    await db.flush()

    return result


@router.get("/{book_id}/query")
async def query(
    q: str,
    k: int = 5,
    book: Book = Depends(get_book_for_user),
    embedding_config: EmbeddingConfig = Depends(get_embedding_config),
):
    return query_book(book, q, embedding_config, k=k)
