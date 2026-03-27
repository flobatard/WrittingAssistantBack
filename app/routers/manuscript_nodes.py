from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependancies import get_book_for_user
from app.models.book import Book
from app.models.manuscript_node import ManuscriptNode
from app.schemas.manuscript_node import ManuscriptNodeCreate, ManuscriptNodeRead, ManuscriptNodeUpdate

router = APIRouter(tags=["manuscript_nodes"])


async def _get_node_for_book(book_id: int, node_id: int, db: AsyncSession) -> ManuscriptNode:
    node = await db.get(ManuscriptNode, node_id)
    if not node or node.book_id != book_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return node


@router.post(
    "/{book_id}/manuscript-nodes/",
    response_model=ManuscriptNodeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_node(
    payload: ManuscriptNodeCreate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.parent_id is not None:
        parent = await db.get(ManuscriptNode, payload.parent_id)
        if not parent or parent.book_id != book.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent node not found")

    node = ManuscriptNode(**payload.model_dump(), book_id=book.id)
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return node


@router.get("/{book_id}/manuscript-nodes/", response_model=list[ManuscriptNodeRead])
async def list_nodes(
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ManuscriptNode)
        .where(ManuscriptNode.book_id == book.id)
        .order_by(ManuscriptNode.position)
    )
    return result.scalars().all()


@router.get("/{book_id}/manuscript-nodes/{node_id}", response_model=ManuscriptNodeRead)
async def get_node(
    node_id: int,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_node_for_book(book.id, node_id, db)


@router.put("/{book_id}/manuscript-nodes/{node_id}", response_model=ManuscriptNodeRead)
async def update_node(
    node_id: int,
    payload: ManuscriptNodeUpdate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    node = await _get_node_for_book(book.id, node_id, db)

    if payload.parent_id is not None:
        parent = await db.get(ManuscriptNode, payload.parent_id)
        if not parent or parent.book_id != book.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent node not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(node, field, value)

    await db.flush()
    await db.refresh(node)
    return node


@router.delete("/{book_id}/manuscript-nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: int,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    node = await _get_node_for_book(book.id, node_id, db)
    await db.delete(node)
