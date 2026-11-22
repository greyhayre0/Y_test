from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from typing import Optional, List
import os
import uuid
import shutil

from app.database import async_session
from app.models import User, Video, Like
from app.schemas import VideoOut
from app.auth import get_current_active_user

router = APIRouter()

# --- 0. Поиск видео ---
@router.get("/videos/search", response_model=List[VideoOut])
async def search_videos(q: str = Query(..., min_length=1), skip: int = 0, limit: int = 50):
    """Поиск видео по названию или описанию."""
    async with async_session() as session:
        # Ищем совпадения в title ИЛИ description
        query = select(Video).where(
            (Video.title.ilike(f"%{q}%")) | (Video.description.ilike(f"%{q}%")),
            Video.is_private == False
        ).order_by(Video.id.desc()).offset(skip).limit(limit)
        
        result = await session.execute(query)
        videos = result.scalars().all()
    
    return videos

from starlette.concurrency import run_in_threadpool
import aiofiles
ALLOWED_EXT = {"mp4", "mov", "webm", "mkv"}
MAX_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
CHUNK = 1024 * 1024  # 1 MB

# --- 4. Лайк / Дизлайк видео --- смена порядка
@router.post("/videos/{video_id}/like")
async def like_video(
    video_id: int,
    current_user: User = Depends(get_current_active_user)
):
    async with async_session() as session:
        # Проверяем, есть ли уже лайк от этого юзера
        result = await session.execute(
            select(Like).where(Like.video_id == video_id, Like.user_id == current_user.id)
        )
        existing_like = result.scalar_one_or_none()

        if existing_like:
            # Убираем лайк
            await session.delete(existing_like)
            await session.execute(
                update(Video).where(Video.id == video_id).values(likes_count=Video.likes_count - 1)
            )
            message = "Лайк убран"
        else:
            # Ставим лайк
            new_like = Like(video_id=video_id, user_id=current_user.id)
            session.add(new_like)
            await session.execute(
                update(Video).where(Video.id == video_id).values(likes_count=Video.likes_count + 1)
            )
            message = "Лайк поставлен"

        await session.commit()
        
        # Получаем актуальное количество
        res = await session.execute(select(Video.likes_count).where(Video.id == video_id))
        likes_count = res.scalar()

    return {"message": message, "likes_count": likes_count}

@router.post("/videos", response_model=VideoOut)
async def upload_video(
    title: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    # 1. Валидация расширения
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Недопустимый формат файла: {ext or 'нет'}")

    # 2. Пути
    os.makedirs("uploads", exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join("uploads", safe_name)
    db_file_path = f"/uploads/{safe_name}"

    # 3. Стриминг с контролем размера
    size = 0
    try:
        async with aiofiles.open(file_path, "wb") as out:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > MAX_SIZE:
                    raise HTTPException(413, "Файл слишком большой")
                await out.write(chunk)
    except HTTPException:
        await run_in_threadpool(lambda: os.path.exists(file_path) and os.remove(file_path))
        raise
    except Exception as e:
        await run_in_threadpool(lambda: os.path.exists(file_path) and os.remove(file_path))
        raise HTTPException(500, f"Ошибка сохранения файла: {e}")
    finally:
        await file.close()

    # 4. Запись в БД + откат файла при ошибке
    try:
        async with async_session() as session:
            new_video = Video(
                title=title,
                description=description,
                file_path=db_file_path,
                owner_id=current_user.id,
            )
            session.add(new_video)
            await session.commit()
            await session.refresh(new_video)
    except Exception as e:
        await run_in_threadpool(lambda: os.path.exists(file_path) and os.remove(file_path))
        raise HTTPException(500, f"Ошибка сохранения в БД: {e}")

    return new_video


# --- 2. Список видео (с поддержкой exclude_id для рекомендаций) ---
@router.get("/videos", response_model=List[VideoOut])
async def list_videos(
    exclude_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    # current_user: User = Depends(get_current_active_user) # Делаем авторизацию опциональной
):
    async with async_session() as session:
        query = select(Video).where(Video.is_private == False)
        
        if exclude_id:
            query = query.where(Video.id != exclude_id)
            
        query = query.order_by(Video.id.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        videos = result.scalars().all()
        
    return videos


# --- 3. Получение одного видео ---
@router.get("/videos/{video_id}", response_model=VideoOut)
async def get_video(video_id: int):
    async with async_session() as session:
        result = await session.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        # Если приватное и не авторизован — не показываем (упрощенно)
        if video.is_private: 
            raise HTTPException(status_code=404, detail="Video not found")
            
    return video


# --- 5. Удаление видео ---
@router.delete("/videos/{video_id}")
async def delete_video(video_id: int, current_user: User = Depends(get_current_active_user)):
    async with async_session() as session:
        result = await session.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        if video.owner_id != current_user.id and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Not authorized")
            
        # Удаляем файл с диска
        file_to_delete = video.file_path.lstrip("/")
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete)
            
        await session.delete(video)
        await session.commit()
        
    return None