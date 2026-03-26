from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_sub
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=UserRead)
async def login(
    sub: str = Depends(get_current_user_sub),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    result = await db.execute(select(User).where(User.oidc_sub == sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(oidc_sub=sub)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return UserRead.model_validate(user)
