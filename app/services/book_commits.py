from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.book_commit import BookCommit
from app.models.manuscript_node import ManuscriptNode
from app.models.manuscript_node_snapshot import ManuscriptNodeSnapshot
from app.schemas.book_commit import CommitRead, RestoreResult


async def create_commit(book: Book, message: str | None, db: AsyncSession) -> CommitRead:
    result = await db.execute(
        select(ManuscriptNode).where(ManuscriptNode.book_id == book.id)
    )
    nodes = result.scalars().all()

    commit = BookCommit(book_id=book.id, message=message)
    db.add(commit)
    await db.flush()

    snapshots = [
        ManuscriptNodeSnapshot(
            commit_id=commit.id,
            front_id=node.front_id,
            parent_front_id=node.parent_front_id,
            node_type=node.node_type,
            title=node.title,
            content=node.content,
            position=node.position,
            is_numbered=node.is_numbered,
            depth_level=node.depth_level,
        )
        for node in nodes
    ]
    db.add_all(snapshots)
    await db.flush()

    return CommitRead(
        id=commit.id,
        book_id=commit.book_id,
        message=commit.message,
        created_at=commit.created_at,
        snapshot_count=len(snapshots),
    )


async def get_commit_with_count(commit_id: int, book_id: int, db: AsyncSession) -> CommitRead:
    commit = await db.get(BookCommit, commit_id)
    if commit is None or commit.book_id != book_id:
        return None

    result = await db.execute(
        select(func.count()).where(ManuscriptNodeSnapshot.commit_id == commit_id)
    )
    count = result.scalar_one()

    return CommitRead(
        id=commit.id,
        book_id=commit.book_id,
        message=commit.message,
        created_at=commit.created_at,
        snapshot_count=count,
    )


async def restore_commit(book: Book, commit_id: int, db: AsyncSession) -> RestoreResult:
    commit = await db.get(BookCommit, commit_id)
    if commit is None or commit.book_id != book.id:
        return None

    snapshots_result = await db.execute(
        select(ManuscriptNodeSnapshot).where(ManuscriptNodeSnapshot.commit_id == commit_id)
    )
    snapshots = snapshots_result.scalars().all()

    count_result = await db.execute(
        select(func.count()).where(ManuscriptNode.book_id == book.id)
    )
    previous_count = count_result.scalar_one()

    existing_result = await db.execute(
        select(ManuscriptNode).where(ManuscriptNode.book_id == book.id)
    )
    for node in existing_result.scalars().all():
        await db.delete(node)
    await db.flush()

    restored_nodes = [
        ManuscriptNode(
            book_id=book.id,
            front_id=snapshot.front_id,
            parent_front_id=snapshot.parent_front_id,
            node_type=snapshot.node_type,
            title=snapshot.title,
            content=snapshot.content,
            position=snapshot.position,
            is_numbered=snapshot.is_numbered,
            depth_level=snapshot.depth_level,
        )
        for snapshot in snapshots
    ]
    db.add_all(restored_nodes)
    await db.flush()

    return RestoreResult(
        commit_id=commit_id,
        nodes_restored=len(restored_nodes),
        nodes_replaced=previous_count,
    )
