import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_optional_user_sub, resolve_user_id
from app.core.database import get_db
from app.core.dependancies import get_book_for_user
from app.models.asset import Asset
from app.models.book import Book
from app.models.manuscript_node import ManuscriptNode
from app.schemas.book import BookRead
from app.schemas.book_io import AssetExport, BookExport, NodeExport

router = APIRouter(tags=["book-io"])


@router.get("/{book_id}/export", response_model=BookExport)
async def export_book(
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    # Eagerly load assets (not configured as selectin on the model)
    result = await db.execute(
        select(Book)
        .where(Book.id == book.id)
        .options(selectinload(Book.assets))
    )
    book = result.scalar_one()
    nodes = [
        NodeExport(
            front_id=n.front_id,
            parent_front_id=n.parent_front_id,
            node_type=n.node_type,
            title=n.title,
            content=n.content,
            position=n.position,
            is_numbered=n.is_numbered,
            depth_level=n.depth_level,
        )
        for n in book.manuscript_nodes
    ]
    assets = [
        AssetExport(
            type=a.type,
            name=a.name,
            aliases=a.aliases,
            short_description=a.short_description,
            attributes=a.attributes,
        )
        for a in book.assets
    ]
    return BookExport(
        title=book.title,
        genre=book.genre,
        is_spinoff=book.is_spinoff,
        ia_settings=book.ia_settings,
        manuscript_nodes=nodes,
        assets=assets,
    )


@router.post("/import", response_model=BookRead, status_code=status.HTTP_201_CREATED)
async def import_book(
    payload: BookExport,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)

    book = Book(
        title=payload.title,
        genre=payload.genre,
        is_spinoff=payload.is_spinoff,
        ia_settings=payload.ia_settings or {},
        user_id=user_id,
    )
    db.add(book)
    await db.flush()

    # Remap front_ids to fresh UUIDs to avoid conflicts with existing nodes
    front_id_map = {n.front_id: uuid.uuid4() for n in payload.manuscript_nodes}

    nodes_without_parent = [n for n in payload.manuscript_nodes if n.parent_front_id is None]
    nodes_with_parent = [n for n in payload.manuscript_nodes if n.parent_front_id is not None]

    for n in nodes_without_parent + nodes_with_parent:
        new_parent = front_id_map.get(n.parent_front_id) if n.parent_front_id else None
        node = ManuscriptNode(
            book_id=book.id,
            front_id=front_id_map[n.front_id],
            parent_front_id=new_parent,
            node_type=n.node_type,
            title=n.title,
            content=n.content,
            position=n.position,
            is_numbered=n.is_numbered,
            depth_level=n.depth_level,
        )
        db.add(node)

    # Flush nodes so FK constraints are satisfied before adding assets
    await db.flush()

    for a in payload.assets:
        asset = Asset(
            book_id=book.id,
            type=a.type,
            name=a.name,
            aliases=a.aliases,
            short_description=a.short_description,
            attributes=a.attributes,
        )
        db.add(asset)

    await db.flush()
    await db.refresh(book)
    return book
