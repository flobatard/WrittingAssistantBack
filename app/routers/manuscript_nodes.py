from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependancies import get_book_for_user
from app.models.book import Book
from app.models.manuscript_node import ManuscriptNode
from app.schemas.manuscript_node import ManuscriptNodeCreate, ManuscriptNodeRead, ManuscriptNodeUpdate, NodeDiff

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


@router.patch("/{book_id}/multiple-manuscript-nodes-update", response_model=list[ManuscriptNodeRead])
async def bulk_update_nodes(
    payload: NodeDiff,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    update_ids = [item.id for item in payload.to_update]
    all_referenced_ids = set(update_ids) | set(payload.to_delete)

    for item in payload.to_create:
        if item.payload.parent_id is not None:
            all_referenced_ids.add(item.payload.parent_id)
    for item in payload.to_update:
        if item.payload.parent_id is not None:
            all_referenced_ids.add(item.payload.parent_id)

    if all_referenced_ids:
        result = await db.execute(
            select(ManuscriptNode.id).where(
                ManuscriptNode.id.in_(all_referenced_ids),
                ManuscriptNode.book_id == book.id,
            )
        )
        found_ids = set(result.scalars().all())
        missing = all_referenced_ids - found_ids
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nodes not found: {missing}")

    # Updates must run before deletes: parent_id CASCADE would wipe children
    # that are being re-parented in the same batch.
    if payload.to_update:
        result = await db.execute(
            select(ManuscriptNode).where(ManuscriptNode.id.in_(update_ids))
        )
        nodes_by_id = {n.id: n for n in result.scalars().all()}
        for item in payload.to_update:
            node = nodes_by_id[item.id]
            for field, value in item.payload.model_dump(exclude_unset=True).items():
                setattr(node, field, value)
        await db.flush()

    if payload.to_delete:
        await db.execute(
            delete(ManuscriptNode).where(ManuscriptNode.id.in_(payload.to_delete))
        )

    new_nodes: list[ManuscriptNode] = []
    if payload.to_create:
        new_nodes = [
            ManuscriptNode(**item.payload.model_dump(), book_id=book.id)
            for item in payload.to_create
        ]
        db.add_all(new_nodes)
        await db.flush()
        for n in new_nodes:
            await db.refresh(n)

    return new_nodes
