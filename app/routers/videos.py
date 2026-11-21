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

'''# --- 1. Создание видео (загрузка файла) ---
@router.post("/videos", response_model=VideoOut)
async def upload_video(
    title: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    # 1. Генерируем безопасное имя файла (чтобы избежать коллизий и проблем с кодировкой)
    os.makedirs("uploads", exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "mp4"
    safe_name = f"{uuid.uuid4()}.{ext}"
    file_path = f"uploads/{safe_name}"
    db_file_path = f"/uploads/{safe_name}" # Путь для отдачи через статику

    # 2. Сначала сохраняем файл на диск
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {e}")

    # 3. Затем создаем запись в БД
    async with async_session() as session:
        new_video = Video(
            title=title,
            description=description,
            file_path=db_file_path,
            owner_id=current_user.id
        )
        session.add(new_video)
        await session.commit()
        await session.refresh(new_video)
    
    return new_video'''

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

# --- 1. Создание видео (загрузка файла) ---
@router.post("/videos", response_model=VideoOut)
async def upload_video(
    title: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    # current_user: User = Depends(get_current_active_user)  <-- ВРЕМЕННО ОТКЛЮЧЕНО
):
    os.makedirs("uploads", exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "mp4"
    safe_name = f"{uuid.uuid4()}.{ext}"
    file_path = f"uploads/{safe_name}"
    db_file_path = f"/uploads/{safe_name}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {e}")

    async with async_session() as session:
        new_video = Video(
            title=title,
            description=description,
            file_path=db_file_path,
            owner_id=1  # <-- ВРЕМЕННО: привязываем к первому пользователю в базе
        )
        session.add(new_video)
        await session.commit()
        await session.refresh(new_video)
    
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


# --- 4. Лайк / Дизлайк видео ---
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