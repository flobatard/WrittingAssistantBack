from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.book_commit import BookCommit
    from app.models.manuscript_node import ManuscriptNode


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    series_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("series.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_book_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )
    position_in_series: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_spinoff: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(255), nullable=True)
    ia_settings: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    embedding_model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_vectorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    manuscript_nodes: Mapped[list["ManuscriptNode"]] = relationship(  # noqa: F821
        "ManuscriptNode",
        back_populates="book",
        order_by="ManuscriptNode.position",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    commits: Mapped[list["BookCommit"]] = relationship(  # noqa: F821
        "BookCommit",
        back_populates="book",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BookCommit.created_at",
    )
    assets: Mapped[list["Asset"]] = relationship(  # noqa: F821
        "Asset",
        back_populates="book",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Asset.name",
    )
