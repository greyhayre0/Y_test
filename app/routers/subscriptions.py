from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, delete

from app.database import get_db
from app.models import User, Subscription, Video
from app.schemas import SubscriptionStatus, ChannelInfo, UserProfileOut
from app.auth import get_current_user

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


async def _subscribers_count(db: AsyncSession, channel_id: int) -> int:
    r = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.channel_id == channel_id)
    )
    return r.scalar() or 0


async def _is_subscribed(db: AsyncSession, subscriber_id: int, channel_id: int) -> bool:
    r = await db.execute(
        select(Subscription.id).where(
            Subscription.subscriber_id == subscriber_id,
            Subscription.channel_id == channel_id,
        )
    )
    return r.scalar_one_or_none() is not None


@router.get("/channel/{channel_id}", response_model=ChannelInfo)
async def get_channel_info(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Информация о канале для страницы видео: подписчики, подписан ли я, мой ли это канал."""
    result = await db.execute(select(User).where(User.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Канал не найден")

    is_own = channel.id == current_user.id
    is_sub = False if is_own else await _is_subscribed(db, current_user.id, channel_id)
    return ChannelInfo(
        id=channel.id,
        email=channel.email,
        subscribers_count=await _subscribers_count(db, channel_id),
        is_subscribed=is_sub,
        is_own_channel=is_own,
    )


@router.post("/{channel_id}/toggle", response_model=SubscriptionStatus)
async def toggle_subscription(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Подписаться/отписаться. Возвращает новое состояние."""
    if channel_id == current_user.id:
        raise HTTPException(400, "Нельзя подписаться на себя")

    result = await db.execute(select(User).where(User.id == channel_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Канал не найден")

    existing = await db.execute(
        select(Subscription).where(
            Subscription.subscriber_id == current_user.id,
            Subscription.channel_id == channel_id,
        )
    )
    sub = existing.scalar_one_or_none()

    if sub:
        await db.delete(sub)
        is_sub = False
    else:
        db.add(Subscription(
            subscriber_id=current_user.id,
            channel_id=channel_id,
        ))
        is_sub = True

    await db.commit()
    return SubscriptionStatus(
        is_subscribed=is_sub,
        subscribers_count=await _subscribers_count(db, channel_id),
    )


@router.get("/my", response_model=list[UserProfileOut])
async def my_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список каналов, на которые подписан текущий пользователь."""
    result = await db.execute(
        select(User)
        .join(Subscription, Subscription.channel_id == User.id)
        .where(Subscription.subscriber_id == current_user.id)
        .order_by(Subscription.created_at.desc())
    )
    channels = result.scalars().all()

    out = []
    for ch in channels:
        cnt = await db.execute(
            select(func.count(Video.id)).where(Video.owner_id == ch.id)
        )
        out.append(UserProfileOut(
            id=ch.id,
            email=ch.email,
            role=ch.role,
            created_at=ch.created_at,
            subscribers_count=await _subscribers_count(db, ch.id),
            subscriptions_count=0,
            videos_count=cnt.scalar() or 0,
        ))
    return out