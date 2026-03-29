from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.book_commit import BookCommit


class ManuscriptNodeSnapshot(Base):
    __tablename__ = "manuscript_node_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    commit_id: Mapped[int] = mapped_column(
        ForeignKey("book_commits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    front_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_front_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[float] = mapped_column(Float, nullable=False)
    is_numbered: Mapped[bool] = mapped_column(Boolean, nullable=False)
    depth_level: Mapped[int] = mapped_column(Integer, nullable=False)

    commit: Mapped[BookCommit] = relationship("BookCommit", back_populates="snapshots")
