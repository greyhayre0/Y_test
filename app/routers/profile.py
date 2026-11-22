# app/routers/profile.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.database import get_db
from app.models import User, Video, Like
from app.schemas import UserProfileOut, VideoOut, UserUpdate
from app.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])


async def _videos_count(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(func.count(Video.id)).where(Video.owner_id == user_id)
    )
    return result.scalar() or 0


@router.get("/me", response_model=UserProfileOut)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    videos_count = await _videos_count(db, current_user.id)
    return UserProfileOut(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        created_at=current_user.created_at,
        subscribers_count=0,
        videos_count=videos_count,
    )


@router.get("/{user_id}", response_model=UserProfileOut)
async def get_user_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    videos_count = await _videos_count(db, user.id)
    return UserProfileOut(
        id=user.id,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
        subscribers_count=0,
        videos_count=videos_count,
    )


@router.get("/{user_id}/videos", response_model=list[VideoOut])
async def get_user_videos(
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Video)
        .where(Video.owner_id == user_id)
        .order_by(Video.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    videos = result.scalars().all()

    out = []
    for v in videos:
        likes_res = await db.execute(
            select(func.count(Like.id)).where(Like.video_id == v.id)
        )
        likes_count = likes_res.scalar() or 0
        out.append(VideoOut(
            id=v.id,
            title=v.title,
            description=v.description,
            file_path=v.file_path,
            owner_id=v.owner_id,
            is_private=getattr(v, "is_private", False),
            created_at=v.created_at.isoformat() if v.created_at else None,
            likes_count=likes_count,
            views=getattr(v, "views", 0) or 0,
            thumbnail_path=getattr(v, "thumbnail_path", None),
            duration=getattr(v, "duration", "0:00") or "0:00",
        ))
    return out


@router.patch("/me", response_model=UserProfileOut)
async def update_my_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.email:
        exists = await db.execute(
            select(User).where(User.email == payload.email, User.id != current_user.id)
        )
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email уже занят")
        current_user.email = payload.email
        await db.commit()
        await db.refresh(current_user)

    videos_count = await _videos_count(db, current_user.id)
    return UserProfileOut(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        created_at=current_user.created_at,
        subscribers_count=0,
        videos_count=videos_count,
    )

# app/routers/profile.py
from pydantic import BaseModel

class PrivacyBulkUpdate(BaseModel):
    is_private: bool

@router.patch("/me/videos/privacy")
async def set_my_videos_privacy(
    payload: PrivacyBulkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        update(Video)
        .where(Video.owner_id == current_user.id)
        .values(is_private=payload.is_private)
    )
    await db.commit()
    return {"ok": True, "is_private": payload.is_private}