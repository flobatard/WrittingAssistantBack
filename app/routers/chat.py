import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user_sub, resolve_user_id
from app.core.database import get_db
from app.core.dependancies import ChatConfig, EmbeddingConfig, get_chat_config, get_embedding_config
from app.models.book import Book
from app.models.conversation import ChatEvent, Conversation
from app.models.manuscript_node import ManuscriptNode
from app.schemas.conversation import (
    ChatEventRead,
    ConversationChatRequest,
    ConversationChatResponse,
    ConversationRead,
    MessageChatResponse,
    ResumeAgentRequest,
    ResumeAgentResponse,
)
from app.services.book_commits import create_commit
from app.services.chat import (
    _AGENTIC_SYSTEM,
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


def _events_to_lc_messages(events: list[ChatEvent]) -> list:
    """Convert ordered ChatEvent rows into LangChain messages for history reconstruction."""
    result = []
    for e in events:
        if e.role == "user":
            result.append(HumanMessage(content=e.content))
        elif e.role == "assistant":
            if e.tool_calls:
                result.append(AIMessage(content=e.content or "", tool_calls=e.tool_calls))
            else:
                result.append(AIMessage(content=e.content or ""))
        elif e.role == "tool":
            result.append(ToolMessage(content=e.content, tool_call_id=e.tool_call_id or "unknown"))
    return result


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


@router.get("/{book_id}/conversations/{conversation_id}/messages", response_model=list[ChatEventRead])
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
        select(ChatEvent)
        .where(ChatEvent.conversation_id == conversation_id)
        .order_by(ChatEvent.id.asc())
    )
    return result.scalars().all()


@router.get("/{book_id}/conversations/{conversation_id}/timeline", response_model=list[ChatEventRead])
async def get_timeline(
    book_id: int,
    conversation_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    await _get_book_or_404(book_id, db, user_id)
    await _get_conversation_or_404(conversation_id, book_id, db)
    result = await db.execute(
        select(ChatEvent)
        .where(ChatEvent.conversation_id == conversation_id)
        .order_by(ChatEvent.id.asc())
    )
    return result.scalars().all()


@router.delete("/{book_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    book_id: int,
    conversation_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    await _get_book_or_404(book_id, db, user_id)
    conversation = await _get_conversation_or_404(conversation_id, book_id, db)
    await db.delete(conversation)
    await db.flush()


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

    title = await asyncio.to_thread(generate_conversation_title, payload.question, chat_config)
    conversation = Conversation(book_id=book_id, title=title)
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)

    user_event = ChatEvent(conversation_id=conversation.id, role="user", content=payload.question, status="done")
    db.add(user_event)
    await db.commit()
    await db.refresh(conversation)

    lc_history = [SystemMessage(content=_AGENTIC_SYSTEM), HumanMessage(content=payload.question)]

    if payload.stream:
        async def streamer():
            conv_data = ConversationRead.model_validate(conversation).model_dump()
            conv_data["start_date"] = conv_data["start_date"].isoformat() if hasattr(conv_data["start_date"], "isoformat") else conv_data["start_date"]
            yield f"event: conversation\ndata: {json.dumps(conv_data)}\n\n"
            yield f"event: conversation_title\ndata: {json.dumps({'title': title})}\n\n"

            async for event in stream_chat_with_book_history_agentic(
                book, lc_history, chat_config, embedding_config, db,
                conversation_id=conversation.id,
            ):
                if event.startswith("event: human_in_the_loop"):
                    yield event
                    return
                else:
                    yield event

        return StreamingResponse(
            streamer(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await chat_with_book_history_agentic(
            book, lc_history, chat_config, embedding_config, db,
            conversation_id=conversation.id,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    final_event_result = await db.execute(
        select(ChatEvent)
        .where(ChatEvent.conversation_id == conversation.id, ChatEvent.role == "assistant")
        .order_by(ChatEvent.id.desc())
        .limit(1)
    )
    final_event = final_event_result.scalar_one()

    return ConversationChatResponse(
        conversation=ConversationRead.model_validate(conversation),
        message=ChatEventRead.model_validate(final_event),
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

    existing_result = await db.execute(
        select(ChatEvent)
        .where(ChatEvent.conversation_id == conversation_id)
        .order_by(ChatEvent.id.asc())
    )
    existing_events = list(existing_result.scalars().all())

    user_event = ChatEvent(conversation_id=conversation.id, role="user", content=payload.question, status="done")
    db.add(user_event)
    await db.flush()

    lc_history = [SystemMessage(content=_AGENTIC_SYSTEM)]
    lc_history.extend(_events_to_lc_messages(existing_events))
    lc_history.append(HumanMessage(content=payload.question))

    if payload.stream:
        async def streamer():
            async for event in stream_chat_with_book_history_agentic(
                book, lc_history, chat_config, embedding_config, db,
                conversation_id=conversation_id,
            ):
                if event.startswith("event: human_in_the_loop"):
                    yield event
                    return
                else:
                    yield event

        return StreamingResponse(
            streamer(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await chat_with_book_history_agentic(
            book, lc_history, chat_config, embedding_config, db,
            conversation_id=conversation_id,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    final_event_result = await db.execute(
        select(ChatEvent)
        .where(ChatEvent.conversation_id == conversation_id, ChatEvent.role == "assistant")
        .order_by(ChatEvent.id.desc())
        .limit(1)
    )
    final_event = final_event_result.scalar_one()

    return MessageChatResponse(
        message=ChatEventRead.model_validate(final_event),
        answer=result["answer"],
        sources=result["sources"],
    )


@router.post("/{book_id}/conversations/{conversation_id}/resume-agent", response_model=ResumeAgentResponse)
async def resume_agent(
    book_id: int,
    conversation_id: int,
    payload: ResumeAgentRequest,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    book = await _get_book_or_404(book_id, db, user_id)
    await _get_conversation_or_404(conversation_id, book_id, db)

    pending_event = await db.get(ChatEvent, payload.chat_event_id)
    if not pending_event or pending_event.conversation_id != conversation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if pending_event.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Event is not pending approval")

    hitl_tc = pending_event.tool_calls[0]
    tool_name = hitl_tc["name"]
    tool_args = hitl_tc["args"]
    llm_tool_call_id = hitl_tc["id"]

    if tool_name == "ask_question":
        if payload.user_decision == "accept":
            user_answer = payload.answer or ""
            observation = (
                f"Observation: The user answered your question.\n"
                f"Question: {tool_args.get('question', '')}\n"
                f"Answer: {user_answer}"
            )
            new_status = "accepted"
        else:
            observation = (
                f"Observation: The user declined to answer your question.\n"
                f"Question: {tool_args.get('question', '')}"
            )
            if payload.feedback:
                observation += f"\nFeedback: {payload.feedback}"
            new_status = "rejected"

    elif payload.user_decision == "accept":
        # Update to database will be made throught front end update of the editor
        observation = f"Observation: The user ACCEPTED the {tool_name} proposal."
        if payload.modified_content is not None:
            observation += " The user provided modified content."
        new_status = "accepted"

    else:
        observation = f"Observation: The user REJECTED the {tool_name} proposal."
        if payload.feedback:
            observation += f" Feedback: {payload.feedback}"
        new_status = "rejected"

    pending_event.status = new_status

    tool_event = ChatEvent(
        conversation_id=conversation_id,
        role="tool",
        content=observation,
        tool_call_id=llm_tool_call_id,
        tool_name=tool_name,
        tool_args=tool_args,
        status=new_status,
    )
    db.add(tool_event)
    await db.flush()

    return ResumeAgentResponse(status=new_status, chat_event_id=pending_event.id)


@router.post("/{book_id}/conversations/{conversation_id}/resume-stream")
async def resume_stream(
    book_id: int,
    conversation_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    chat_config: ChatConfig = Depends(get_chat_config),
    embedding_config: EmbeddingConfig = Depends(get_embedding_config),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    book = await _get_book_or_404(book_id, db, user_id)
    await _get_conversation_or_404(conversation_id, book_id, db)

    events_result = await db.execute(
        select(ChatEvent)
        .where(ChatEvent.conversation_id == conversation_id)
        .order_by(ChatEvent.id.asc())
    )
    all_events = list(events_result.scalars().all())

    lc_history = [SystemMessage(content=_AGENTIC_SYSTEM)]
    lc_history.extend(_events_to_lc_messages(all_events))

    async def streamer():
        async for event in stream_chat_with_book_history_agentic(
            book=book,
            lc_history=lc_history,
            chat_config=chat_config,
            embedding_config=embedding_config,
            db=db,
            conversation_id=conversation_id,
        ):
            if event.startswith("event: human_in_the_loop"):
                yield event
                return
            else:
                yield event

    return StreamingResponse(
        streamer(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
