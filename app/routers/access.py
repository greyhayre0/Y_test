import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from jose import JWTError, jwt  # если у вас PyJWT — см. заметку ниже
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user  # поправь путь под свой проект
from app.config import settings
from app.database import get_db
from app.models import User, Video, VideoAccess

router = APIRouter(tags=["access"])


# ---------- Пользователь или аноним (header ИЛИ ?token= для <video>) ----------

async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:]
    elif request.query_params.get("token"):
        token = request.query_params["token"]
    if not token:
        return None
    try:
        # ПОДГОНИ под свой auth.py: имя секрета, алгоритм, поле с email
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[getattr(settings, "ALGORITHM", "HS256")])
        email = payload.get("sub")
        if not email:
            return None
    except JWTError:
        return None
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ---------- Проверка доступа (используется во ВСЕХ эндпоинтах видео) ----------

async def can_view_video(db: AsyncSession, video: Video, user) -> bool:
    if not video.is_private:
        return True
    if user is None:
        return False
    if video.owner_id == user.id:
        return True
    row = await db.execute(
        select(VideoAccess).where(
            VideoAccess.video_id == video.id, VideoAccess.user_id == user.id
        )
    )
    return row.scalar_one_or_none() is not None


async def ensure_can_view(db: AsyncSession, video: Video, user):
    if not await can_view_video(db, video, user):
        # 404, а не 403 — не раскрываем сам факт существования приватного видео
        raise HTTPException(status_code=404, detail="Видео не найдено")


def ensure_owner(video: Video, user: User):
    if video.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Только владелец может управлять доступом")


# ---------- Управление списком доступа (только владелец) ----------

class AccessGrantIn(BaseModel):
    email: str


@router.get("/videos/{video_id}/access")
async def list_access(video_id: int, db: AsyncSession = Depends(get_db),
                      user: User = Depends(get_current_user)):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    ensure_owner(video, user)
    rows = await db.execute(
        select(VideoAccess.user_id, User.email)
        .join(User, VideoAccess.user_id == User.id)
        .where(VideoAccess.video_id == video_id)
        .order_by(VideoAccess.id)
    )
    return [{"user_id": uid, "email": email} for uid, email in rows.all()]


@router.post("/videos/{video_id}/access")
async def grant_access(video_id: int, payload: AccessGrantIn,
                       db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    ensure_owner(video, user)

    email = payload.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="Укажите email")
    target = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь с таким email не найден")
    if target.id == video.owner_id:
        raise HTTPException(status_code=400, detail="Владелец и так имеет доступ")

    existing = (await db.execute(
        select(VideoAccess).where(VideoAccess.video_id == video_id, VideoAccess.user_id == target.id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="У этого пользователя уже есть доступ")

    db.add(VideoAccess(video_id=video_id, user_id=target.id))
    await db.commit()
    return {"ok": True, "user_id": target.id, "email": target.email}


@router.delete("/videos/{video_id}/access/{user_id}")
async def revoke_access(video_id: int, user_id: int,
                        db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    ensure_owner(video, user)
    await db.execute(
        delete(VideoAccess).where(VideoAccess.video_id == video_id, VideoAccess.user_id == user_id)
    )
    await db.commit()
    return {"ok": True}


# ---------- Защищённая отдача файла (с Range для перемотки) ----------

@router.get("/videos/{video_id}/stream")
async def stream_video(video_id: int, request: Request,
                       db: AsyncSession = Depends(get_db),
                       user=Depends(get_optional_user)):
    video = await db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    await ensure_can_view(db, video, user)

    if not video.file_path:
        raise HTTPException(status_code=404, detail="Файл не найден")
    path = Path(video.file_path.lstrip("/"))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")

    size = path.stat().st_size
    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if m:
            start_s, end_s = m.groups()
            start = int(start_s) if start_s else 0
            end = min(int(end_s), size - 1) if end_s else size - 1
            if start >= size or start > end:
                raise HTTPException(status_code=416, headers={"Content-Range": f"bytes */{size}"})
            length = end - start + 1

            def iterfile():
                with open(path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            return StreamingResponse(
                iterfile(), status_code=206, media_type="video/mp4",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{size}",
                    "Content-Length": str(length),
                    "Accept-Ranges": "bytes",
                },
            )
    return FileResponse(path, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})