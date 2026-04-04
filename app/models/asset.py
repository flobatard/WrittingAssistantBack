from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.book import Book


class AssetType(str, enum.Enum):
    CHARACTER = "CHARACTER"
    LOCATION  = "LOCATION"
    ITEM      = "ITEM"
    FACTION   = "FACTION"
    LORE      = "LORE"
    IMAGE     = "IMAGE"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        server_default=text("gen_random_uuid()"),
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[AssetType] = mapped_column(Enum(AssetType), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # PostgreSQL native array; server default avoids NULL on insertion without aliases
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        server_default=text("ARRAY[]::text[]"),
    )
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSONB for arbitrary per-type attributes (e.g. age/role for characters, coordinates for locations)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    book: Mapped["Book"] = relationship("Book", back_populates="assets")
