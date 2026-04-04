from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependancies import get_book_for_user
from app.models.asset import Asset, AssetType
from app.models.book import Book
from app.schemas.asset import AssetCreate, AssetRead, AssetUpdate

router = APIRouter(tags=["assets"])


async def _get_asset_for_book(book_id: int, asset_id: UUID, db: AsyncSession) -> Asset:
    """Fetch an asset by UUID while ensuring it belongs to the given book."""
    result = await db.execute(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.book_id == book_id,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@router.get("/{book_id}/assets/", response_model=list[AssetRead])
async def list_assets(
    book: Book = Depends(get_book_for_user),
    asset_type: AssetType | None = Query(default=None, alias="type"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Asset).where(Asset.book_id == book.id)
    if asset_type is not None:
        stmt = stmt.where(Asset.type == asset_type)
    stmt = stmt.order_by(Asset.name)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{book_id}/assets/", response_model=AssetRead, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    asset = Asset(**payload.model_dump(), book_id=book.id)
    db.add(asset)
    await db.flush()
    await db.refresh(asset)
    return asset


@router.get("/{book_id}/assets/{asset_id}", response_model=AssetRead)
async def get_asset(
    asset_id: UUID,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_asset_for_book(book.id, asset_id, db)


@router.put("/{book_id}/assets/{asset_id}", response_model=AssetRead)
async def update_asset(
    asset_id: UUID,
    payload: AssetUpdate,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await _get_asset_for_book(book.id, asset_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(asset, field, value)
    await db.flush()
    await db.refresh(asset)
    return asset


@router.delete("/{book_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await _get_asset_for_book(book.id, asset_id, db)
    await db.delete(asset)
