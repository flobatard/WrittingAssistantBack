from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.manuscript_node_snapshot import ManuscriptNodeSnapshot


class BookCommit(Base):
    __tablename__ = "book_commits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    book: Mapped[Book] = relationship("Book", back_populates="commits")
    snapshots: Mapped[list[ManuscriptNodeSnapshot]] = relationship(
        "ManuscriptNodeSnapshot",
        back_populates="commit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
