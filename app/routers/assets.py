import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependancies import get_book_for_user
from app.core.s3 import delete_object, delete_objects_by_prefix, generate_presigned_download_url, generate_presigned_upload_url
from app.models.asset import Asset, AssetType
from app.models.book import Book
from app.schemas.asset import (
    AssetCreate,
    AssetRead,
    AssetUpdate,
    DownloadUrlRequest,
    PresignedDownloadResponse,
    PresignedUploadResponse,
    UploadUrlRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assets"])

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
    "image/svg+xml",
    "application/pdf",
}


def _asset_prefix(book_id: int, asset_id: UUID) -> str:
    return f"books/{book_id}/assets/{asset_id}/"


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
    try:
        delete_objects_by_prefix(_asset_prefix(book.id, asset.id))
    except Exception:
        logger.warning("Failed to delete S3 folder for asset %s", asset.id, exc_info=True)
    await db.delete(asset)


@router.post(
    "/{book_id}/assets/{asset_id}/delete-file",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_asset_file(
    asset_id: UUID,
    payload: DownloadUrlRequest,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_asset_for_book(book.id, asset_id, db)

    expected_prefix = _asset_prefix(book.id, asset_id)
    if not payload.object_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Object key does not belong to this asset",
        )

    delete_object(payload.object_key)


@router.post(
    "/{book_id}/assets/{asset_id}/upload-url",
    response_model=PresignedUploadResponse,
)
async def generate_upload_url(
    asset_id: UUID,
    payload: UploadUrlRequest,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{payload.content_type}' is not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    await _get_asset_for_book(book.id, asset_id, db)

    object_key = f"{_asset_prefix(book.id, asset_id)}{payload.filename}"
    settings = get_settings()
    upload_url = generate_presigned_upload_url(object_key, payload.content_type)

    return PresignedUploadResponse(
        upload_url=upload_url,
        object_key=object_key,
        expires_in=settings.S3_PRESIGNED_EXPIRY,
    )


@router.post(
    "/{book_id}/assets/{asset_id}/download-url",
    response_model=PresignedDownloadResponse,
)
async def generate_download_url(
    asset_id: UUID,
    payload: DownloadUrlRequest,
    book: Book = Depends(get_book_for_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_asset_for_book(book.id, asset_id, db)

    expected_prefix = _asset_prefix(book.id, asset_id)
    if not payload.object_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Object key does not belong to this asset",
        )

    settings = get_settings()
    download_url = generate_presigned_download_url(payload.object_key)

    return PresignedDownloadResponse(
        download_url=download_url,
        expires_in=settings.S3_PRESIGNED_EXPIRY,
    )
