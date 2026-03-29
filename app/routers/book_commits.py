from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependancies import get_book_for_user
from app.models.book import Book
from app.models.book_commit import BookCommit
from app.models.manuscript_node_snapshot import ManuscriptNodeSnapshot
from app.schemas.book import BookRead
from app.schemas.book_commit import (
    CommitCreate,
    CommitRead,
    ManuscriptNodeSnapshotRead,
)
from app.services.book_commits import create_commit, get_commit_with_count, restore_commit

router = APIRouter(tags=["book_commits"])


async def _get_commit_for_book(commit_id: int, book_id: int, db: AsyncSession) -> BookCommit:
    commit = await db.get(BookCommit, commit_id)
    if commit is None or commit.book_id != book_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commit not found")
    return commit


@router.post(
    "/{book_id}/commits",
    response_model=CommitRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_book_commit(
    payload: CommitCreate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_commit(book, payload.message, db)


@router.get("/{book_id}/commits", response_model=list[CommitRead])
async def list_book_commits(
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            BookCommit.id,
            BookCommit.book_id,
            BookCommit.message,
            BookCommit.created_at,
            func.count(ManuscriptNodeSnapshot.id).label("snapshot_count"),
        )
        .outerjoin(ManuscriptNodeSnapshot, ManuscriptNodeSnapshot.commit_id == BookCommit.id)
        .where(BookCommit.book_id == book.id)
        .group_by(BookCommit.id)
        .order_by(BookCommit.created_at.desc())
    )
    rows = result.all()
    return [
        CommitRead(
            id=row.id,
            book_id=row.book_id,
            message=row.message,
            created_at=row.created_at,
            snapshot_count=row.snapshot_count,
        )
        for row in rows
    ]


@router.get("/{book_id}/commits/{commit_id}", response_model=CommitRead)
async def get_book_commit(
    commit_id: int,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    commit_read = await get_commit_with_count(commit_id, book.id, db)
    if commit_read is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commit not found")
    return commit_read


@router.get("/{book_id}/commits/{commit_id}/nodes", response_model=list[ManuscriptNodeSnapshotRead])
async def get_commit_nodes(
    commit_id: int,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_commit_for_book(commit_id, book.id, db)
    result = await db.execute(
        select(ManuscriptNodeSnapshot)
        .where(ManuscriptNodeSnapshot.commit_id == commit_id)
        .order_by(ManuscriptNodeSnapshot.position)
    )
    return result.scalars().all()


@router.post("/{book_id}/commits/{commit_id}/restore", response_model=BookRead)
async def restore_book_commit(
    commit_id: int,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    result = await restore_commit(book, commit_id, db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commit not found")
    return result


@router.delete("/{book_id}/commits/{commit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book_commit(
    commit_id: int,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    commit = await _get_commit_for_book(commit_id, book.id, db)
    await db.delete(commit)
