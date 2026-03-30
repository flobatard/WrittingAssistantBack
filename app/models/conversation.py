from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChatToolCall(Base):
    __tablename__ = "chat_tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    args: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    called_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # HITL fields
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")  # completed | pending_approval | accepted | rejected
    llm_tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_message_dump: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    emit_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    author: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant" | "tool"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # HITL: links a "tool" author message back to the ChatToolCall for history reconstruction
    tool_call_id: Mapped[int | None] = mapped_column(ForeignKey("chat_tool_calls.id", ondelete="SET NULL"), nullable=True, index=True)
