import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user_sub, resolve_user_id
from app.core.database import get_db
from app.models.book import Book
from app.schemas.book import BookCreate, BookRead, BookUpdate, ChatRequest, ChatResponse
from app.services.rag import vectorize_book, query_book
from app.services.chat import chat_with_book, stream_chat_with_book

from app.core.dependancies import get_embedding_config, EmbeddingConfig, get_chat_config, ChatConfig

router = APIRouter(tags=["books"])


def _check_book_access(book: Book, user_id: int | None) -> None:
    """Lève 403 si l'utilisateur n'a pas accès au livre."""
    if book.user_id is not None and book.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


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
    book_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    user_id = await resolve_user_id(sub, db)
    _check_book_access(book, user_id)
    return book


@router.put("/{book_id}", response_model=BookRead)
async def update_book(
    book_id: int,
    payload: BookUpdate,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    user_id = await resolve_user_id(sub, db)
    _check_book_access(book, user_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(book, field, value)

    await db.flush()
    await db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    user_id = await resolve_user_id(sub, db)
    _check_book_access(book, user_id)
    await db.delete(book)


@router.post("/{book_id}/vectorize")
async def vectorize(
        book_id: int,
        sub: str | None = Depends(get_optional_user_sub),
        embedding_config: EmbeddingConfig = Depends(get_embedding_config),
        db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    user_id = await resolve_user_id(sub, db)
    _check_book_access(book, user_id)

    result = vectorize_book(book, embedding_config)

    # Mémorise le modèle utilisé
    book.embedding_model_used = result["collection_name"].split("_", 2)[-1] if "_" in result["collection_name"] else None
    await db.flush()

    return result


@router.get("/{book_id}/query")
async def query(
        book_id: int,
        q: str,
        k: int = 5,
        sub: str | None = Depends(get_optional_user_sub),
        embedding_config: EmbeddingConfig = Depends(get_embedding_config),
        db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    user_id = await resolve_user_id(sub, db)
    _check_book_access(book, user_id)

    return query_book(book, q, embedding_config, k=k)