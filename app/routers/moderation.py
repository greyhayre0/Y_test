from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Comment, Like, Report, User, Video
from app.auth import get_current_user  # <-- поправь под свой проект, см. заметку ниже

router = APIRouter(tags=["moderation"])

MODERATOR_ROLES = {"moderator", "admin"}


def require_moderator(user: User) -> User:
    if (user.role or "user") not in MODERATOR_ROLES:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return user


class ReportIn(BaseModel):
    reason: str


# ---------- Удаление комментариев ----------
# Право есть у: автора комментария, владельца видео, модератора, админа

@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Комментарий не найден")

    video = await db.get(Video, comment.video_id)
    is_video_owner = video is not None and video.owner_id == user.id
    is_author = comment.user_id == user.id

    if not (is_author or is_video_owner or (user.role or "user") in MODERATOR_ROLES):
        raise HTTPException(status_code=403, detail="Нет прав на удаление этого комментария")

    await db.delete(comment)
    await db.commit()
    return {"ok": True}


# ---------- Жалобы на видео ----------

@router.post("/videos/{video_id}/report")
async def report_video(
    video_id: int,
    payload: ReportIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Укажите причину жалобы")
    if len(reason) > 1000:
        raise HTTPException(status_code=400, detail="Причина слишком длинная (макс. 1000 символов)")

    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")

    existing = await db.execute(
        select(Report).where(
            Report.video_id == video_id,
            Report.user_id == user.id,
            Report.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Вы уже отправляли жалобу на это видео")

    report = Report(video_id=video_id, user_id=user.id, reason=reason, video_title=video.title)
    db.add(report)
    await db.commit()
    return {"ok": True, "id": report.id}


@router.get("/reports/pending")
async def pending_reports(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_moderator(user)
    rows = await db.execute(
        select(Report, User.email, Video.title)
        .join(User, Report.user_id == User.id)
        .outerjoin(Video, Report.video_id == Video.id)
        .where(Report.status == "pending")
        .order_by(Report.id.desc())
    )
    return [
        {
            "id": r.id,
            "video_id": r.video_id,
            "video_title": v_title or r.video_title or "Видео удалено",
            "reporter_email": email,
            "reason": r.reason,
            "created_at": r.created_at,
        }
        for r, email, v_title in rows.all()
    ]


@router.post("/reports/{report_id}/approve")
async def approve_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_moderator(user)
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Жалоба не найдена")
    if report.status != "pending":
        raise HTTPException(status_code=400, detail="Жалоба уже обработана")

    now = datetime.now().isoformat()
    video = await db.get(Video, report.video_id) if report.video_id else None

    if video:
        # У старых таблиц нет ON DELETE CASCADE — чистим связанные строки явно
        await db.execute(delete(Comment).where(Comment.video_id == video.id))
        await db.execute(delete(Like).where(Like.video_id == video.id))
        # Все активные жалобы на это видео закрываем разом
        await db.execute(
            update(Report)
            .where(Report.video_id == video.id, Report.status == "pending")
            .values(status="approved", reviewed_by=user.id, reviewed_at=now)
        )
        file_path = video.file_path
        await db.delete(video)  # reports.video_id автоматически станет NULL
        await db.commit()

        # Файл удаляем только после успешного коммита
        if file_path and file_path.startswith("/uploads/"):
            try:
                Path(file_path.lstrip("/")).unlink(missing_ok=True)
            except OSError:
                pass
    else:
        # Видео уже удалено (например, владельцем) — просто закрываем жалобу
        report.status = "approved"
        report.reviewed_by = user.id
        report.reviewed_at = now
        await db.commit()

    return {"ok": True, "video_deleted": video is not None}


@router.post("/reports/{report_id}/reject")
async def reject_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_moderator(user)
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Жалоба не найдена")
    if report.status != "pending":
        raise HTTPException(status_code=400, detail="Жалоба уже обработана")

    report.status = "rejected"
    report.reviewed_by = user.id
    report.reviewed_at = datetime.now().isoformat()
    await db.commit()
    return {"ok": True}