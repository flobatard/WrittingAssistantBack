from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_optional_user_sub, resolve_user_id
from app.core.database import get_db
from app.models.series import Series
from app.schemas.series import SeriesCreate, SeriesRead, SeriesUpdate

router = APIRouter(tags=["series"])


def _check_series_access(series: Series, user_id: int | None) -> None:
    if series.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.post("/", response_model=SeriesRead, status_code=status.HTTP_201_CREATED)
async def create_series(
    payload: SeriesCreate,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    series = Series(**payload.model_dump(), user_id=user_id)
    db.add(series)
    await db.flush()
    await db.refresh(series)
    return series


@router.get("/", response_model=list[SeriesRead])
async def list_series(
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    user_id = await resolve_user_id(sub, db)
    result = await db.execute(
        select(Series)
        .where(Series.user_id == user_id)
        .order_by(Series.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{series_id}", response_model=SeriesRead)
async def get_series(
    series_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    series = await db.get(Series, series_id)
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    user_id = await resolve_user_id(sub, db)
    _check_series_access(series, user_id)
    return series


@router.put("/{series_id}", response_model=SeriesRead)
async def update_series(
    series_id: int,
    payload: SeriesUpdate,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    series = await db.get(Series, series_id)
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    user_id = await resolve_user_id(sub, db)
    _check_series_access(series, user_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(series, field, value)

    await db.flush()
    await db.refresh(series)
    return series


@router.delete("/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series(
    series_id: int,
    sub: str | None = Depends(get_optional_user_sub),
    db: AsyncSession = Depends(get_db),
):
    series = await db.get(Series, series_id)
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    user_id = await resolve_user_id(sub, db)
    _check_series_access(series, user_id)
    await db.delete(series)
