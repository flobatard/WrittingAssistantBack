import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.book import Book
from app.schemas.book import BookCreate, BookRead, BookUpdate, ChatRequest, ChatResponse
from app.services.rag import vectorize_book, query_book
from app.services.chat import chat_with_book, stream_chat_with_book

from app.core.dependancies import get_embedding_config, EmbeddingConfig, get_chat_config, ChatConfig

router = APIRouter(tags=["books"])


@router.post("/", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def create_book(payload: BookCreate, db: AsyncSession = Depends(get_db)):
    book = Book(**payload.model_dump())
    db.add(book)
    await db.flush()
    await db.refresh(book)
    return book


@router.get("/", response_model=list[BookRead])
async def list_books(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Book).order_by(Book.created_at.desc()))
    return result.scalars().all()


@router.get("/{book_id}", response_model=BookRead)
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


@router.put("/{book_id}", response_model=BookRead)
async def update_book(
    book_id: int, payload: BookUpdate, db: AsyncSession = Depends(get_db)
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(book, field, value)

    await db.flush()
    await db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    await db.delete(book)


@router.post("/{book_id}/vectorize")
async def vectorize(
        book_id: int, 
        embedding_config: EmbeddingConfig = Depends(get_embedding_config),
        db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

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
        embedding_config: EmbeddingConfig = Depends(get_embedding_config),
        db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    return query_book(book, q, embedding_config, k=k)


@router.post("/{book_id}/chat")
async def chat(
        book_id: int,
        payload: ChatRequest,
        chat_config: ChatConfig = Depends(get_chat_config),
        embedding_config: EmbeddingConfig = Depends(get_embedding_config),
        db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    if not book.embedding_model_used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Book not vectorized yet. Call POST /books/{id}/vectorize first.")

    if payload.stream:
        return StreamingResponse(
            stream_chat_with_book(book, payload.question, payload.k, chat_config, embedding_config),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await asyncio.to_thread(chat_with_book, book, payload.question, payload.k, chat_config, embedding_config)
    return ChatResponse(**result)
