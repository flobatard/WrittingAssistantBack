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


class ChatEvent(Base):
    __tablename__ = "chat_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)           # "user" | "assistant" | "tool"
    content: Mapped[str | None] = mapped_column(Text, nullable=True)        # null for pure tool-call AIMessages
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)    # [{id, name, args, type}]
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # LLM-internal ID (ToolMessage rows)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_args: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="done")  # done | pending | accepted | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
