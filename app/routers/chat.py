import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user_sub, resolve_user_id
from app.core.database import get_db
from app.core.dependancies import ChatConfig, EmbeddingConfig, get_chat_config, get_embedding_config
from app.models.book import Book
from app.models.conversation import ChatMessage, Conversation
from app.schemas.conversation import (
    ChatMessageRead,
    ConversationChatRequest,
    ConversationChatResponse,
    ConversationRead,
    MessageChatResponse,
)
from app.services.chat import (
    chat_with_book_history_agentic,
    generate_conversation_title,
    stream_chat_with_book_history_agentic,
)

router = APIRouter(tags=["conversations"])


async def _get_book_or_404(book_id: int, db: AsyncSession, user_id: int | None = None) -> Book:
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    if book.user_id is not None and book.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return book


async def _get_conversation_or_404(conversation_id: int, book_id: int, db: AsyncSession) -> Conversation:
    conversation = await db.get(Conversation, conversation_id)
    if not conversation or conversation.book_id != book_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.get("/{book_id}/conversations", response_model=list[ConversationRead])
async def list_conversations(
    book_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    await _get_book_or_404(book_id, db, user_id)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.book_id == book_id)
        .order_by(Conversation.start_date.desc())
    )
    return result.scalars().all()


@router.get("/{book_id}/conversations/{conversation_id}/messages", response_model=list[ChatMessageRead])
async def list_messages(
    book_id: int,
    conversation_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    await _get_book_or_404(book_id, db, user_id)
    await _get_conversation_or_404(conversation_id, book_id, db)
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.emit_date.asc())
    )
    return result.scalars().all()


@router.post("/{book_id}/conversations", response_model=ConversationChatResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    book_id: int,
    payload: ConversationChatRequest,
    sub: str | None = Depends(get_optional_user_sub),
    chat_config: ChatConfig = Depends(get_chat_config),
    embedding_config: EmbeddingConfig = Depends(get_embedding_config),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    book = await _get_book_or_404(book_id, db, user_id)
    if not book.embedding_model_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book not vectorized yet. Call POST /books/{id}/vectorize first.",
        )

    conversation = Conversation(book_id=book_id)
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)

    user_msg = ChatMessage(conversation_id=conversation.id, author="user", content=payload.question)
    db.add(user_msg)
    await db.flush()
    await db.refresh(user_msg)

    if payload.stream:
        async def streamer():
            full_response = ""
            async for event in stream_chat_with_book_history_agentic(book, payload.question, [], chat_config, embedding_config, db):
                yield event
                if '"full_response"' in event:
                    import json as _json
                    data = _json.loads(event.split("data: ", 1)[1])
                    full_response = data.get("full_response", "")
            assistant_msg = ChatMessage(conversation_id=conversation.id, author="assistant", content=full_response)
            db.add(assistant_msg)
            title = await asyncio.to_thread(generate_conversation_title, payload.question, full_response, chat_config)
            conversation.title = title
            await db.flush()

        return StreamingResponse(
            streamer(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await chat_with_book_history_agentic(
        book, payload.question, [], chat_config, embedding_config, db
    )

    assistant_msg = ChatMessage(conversation_id=conversation.id, author="assistant", content=result["answer"])
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    title = await asyncio.to_thread(generate_conversation_title, payload.question, result["answer"], chat_config)
    conversation.title = title
    await db.flush()
    await db.refresh(conversation)

    return ConversationChatResponse(
        conversation=ConversationRead.model_validate(conversation),
        message=ChatMessageRead.model_validate(assistant_msg),
        answer=result["answer"],
        sources=result["sources"],
    )


@router.post("/{book_id}/conversations/{conversation_id}/messages", response_model=MessageChatResponse)
async def send_message(
    book_id: int,
    conversation_id: int,
    payload: ConversationChatRequest,
    sub: str | None = Depends(get_optional_user_sub),
    chat_config: ChatConfig = Depends(get_chat_config),
    embedding_config: EmbeddingConfig = Depends(get_embedding_config),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    book = await _get_book_or_404(book_id, db, user_id)
    if not book.embedding_model_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Book not vectorized yet. Call POST /books/{id}/vectorize first.",
        )
    conversation = await _get_conversation_or_404(conversation_id, book_id, db)

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.emit_date.asc())
    )
    history = list(history_result.scalars().all())

    user_msg = ChatMessage(conversation_id=conversation.id, author="user", content=payload.question)
    db.add(user_msg)
    await db.flush()

    if payload.stream:
        async def streamer():
            full_response = ""
            async for event in stream_chat_with_book_history_agentic(book, payload.question, history, chat_config, embedding_config, db):
                yield event
                if '"full_response"' in event:
                    import json as _json
                    data = _json.loads(event.split("data: ", 1)[1])
                    full_response = data.get("full_response", "")
            assistant_msg = ChatMessage(conversation_id=conversation.id, author="assistant", content=full_response)
            db.add(assistant_msg)
            await db.flush()

        return StreamingResponse(
            streamer(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    result = await chat_with_book_history_agentic(
        book, payload.question, history, chat_config, embedding_config, db
    )

    assistant_msg = ChatMessage(conversation_id=conversation.id, author="assistant", content=result["answer"])
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    return MessageChatResponse(
        message=ChatMessageRead.model_validate(assistant_msg),
        answer=result["answer"],
        sources=result["sources"],
    )
