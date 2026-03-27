from uuid import UUID

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


async def _get_node_by_front_id(book_id: int, front_id: UUID, db: AsyncSession) -> ManuscriptNode:
    result = await db.execute(
        select(ManuscriptNode).where(
            ManuscriptNode.front_id == front_id,
            ManuscriptNode.book_id == book_id,
        )
    )
    node = result.scalar_one_or_none()
    if node is None:
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
    if payload.parent_front_id is not None:
        result = await db.execute(
            select(ManuscriptNode).where(
                ManuscriptNode.front_id == payload.parent_front_id,
                ManuscriptNode.book_id == book.id,
            )
        )
        if result.scalar_one_or_none() is None:
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

    if payload.parent_front_id is not None:
        result = await db.execute(
            select(ManuscriptNode).where(
                ManuscriptNode.front_id == payload.parent_front_id,
                ManuscriptNode.book_id == book.id,
            )
        )
        if result.scalar_one_or_none() is None:
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


@router.get("/{book_id}/manuscript-nodes/by-front-id/{front_id}", response_model=ManuscriptNodeRead)
async def get_node_by_front_id(
    front_id: UUID,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_node_by_front_id(book.id, front_id, db)


@router.put("/{book_id}/manuscript-nodes/by-front-id/{front_id}", response_model=ManuscriptNodeRead)
async def update_node_by_front_id(
    front_id: UUID,
    payload: ManuscriptNodeUpdate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    node = await _get_node_by_front_id(book.id, front_id, db)

    if payload.parent_front_id is not None:
        result = await db.execute(
            select(ManuscriptNode).where(
                ManuscriptNode.front_id == payload.parent_front_id,
                ManuscriptNode.book_id == book.id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent node not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(node, field, value)

    await db.flush()
    await db.refresh(node)
    return node


@router.delete(
    "/{book_id}/manuscript-nodes/by-front-id/{front_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_node_by_front_id(
    front_id: UUID,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    node = await _get_node_by_front_id(book.id, front_id, db)
    await db.delete(node)


@router.patch("/{book_id}/multiple-manuscript-nodes-update", response_model=list[ManuscriptNodeRead])
async def bulk_update_nodes(
    payload: NodeDiff,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    all_front_ids = {item.front_id for item in payload.to_update} | set(payload.to_delete)

    if all_front_ids:
        result = await db.execute(
            select(ManuscriptNode.front_id).where(
                ManuscriptNode.front_id.in_(all_front_ids),
                ManuscriptNode.book_id == book.id,
            )
        )
        found_front_ids = set(result.scalars().all())
        missing = all_front_ids - found_front_ids
        if missing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Nodes not found: {missing}")

    parent_front_ids = {
        item.payload.parent_front_id
        for item in (*payload.to_create, *payload.to_update)
        if item.payload.parent_front_id is not None
    }
    if parent_front_ids:
        result = await db.execute(
            select(ManuscriptNode.front_id).where(
                ManuscriptNode.front_id.in_(parent_front_ids),
                ManuscriptNode.book_id == book.id,
            )
        )
        found_parent_ids = set(result.scalars().all())
        missing_parents = parent_front_ids - found_parent_ids
        if missing_parents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent nodes not found: {missing_parents}",
            )

    # Updates must run before deletes: deleting a parent sets parent_front_id to NULL
    # on children; run updates first so re-parented nodes keep their new parent.
    if payload.to_update:
        update_front_ids = [item.front_id for item in payload.to_update]
        result = await db.execute(
            select(ManuscriptNode).where(ManuscriptNode.front_id.in_(update_front_ids))
        )
        nodes_by_front_id = {n.front_id: n for n in result.scalars().all()}
        for item in payload.to_update:
            node = nodes_by_front_id[item.front_id]
            for field, value in item.payload.model_dump(exclude_unset=True).items():
                setattr(node, field, value)
        await db.flush()

    if payload.to_delete:
        await db.execute(
            delete(ManuscriptNode).where(ManuscriptNode.front_id.in_(payload.to_delete))
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
