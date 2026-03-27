from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.book import Book


class ManuscriptNode(Base):
    __tablename__ = "manuscript_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("manuscript_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(String(50), nullable=False, default="chapter")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    is_numbered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    depth_level: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    book: Mapped[Book] = relationship("Book", back_populates="manuscript_nodes")
    children: Mapped[list[ManuscriptNode]] = relationship(
        "ManuscriptNode",
        back_populates="parent",
        order_by="ManuscriptNode.position",
    )
    parent: Mapped[Optional[ManuscriptNode]] = relationship(
        "ManuscriptNode", back_populates="children", remote_side="ManuscriptNode.id"
    )
