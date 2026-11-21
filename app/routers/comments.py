# app/routers/comments.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.database import async_session
from app.models import User, Comment
from app.schemas import CommentCreate, CommentOut
from app.auth import get_current_active_user

router = APIRouter()

# 1. Получение комментариев (доступно всем, без обязательной авторизации)
@router.get("/videos/{video_id}/comments", response_model=List[CommentOut])
async def get_comments(video_id: int):
    async with async_session() as session:
        # Делаем JOIN с таблицей User, чтобы получить email
        query = (
            select(Comment, User.email)
            .join(User, Comment.user_id == User.id)
            .where(Comment.video_id == video_id)
            .order_by(Comment.id.desc())
        )
        result = await session.execute(query)
        
        # Формируем список ответов вручную, так как результат - это кортежи (Comment, email)
        comments = []
        for row in result:
            comment, email = row
            # Создаем объект CommentOut, подставляя email
            comments.append({
                "id": comment.id,
                "text": comment.text,
                "video_id": comment.video_id,
                "user_id": comment.user_id,
                "user_email": email, # <-- Вот наш email
                "created_at": comment.created_at
            })
            
    return comments

# 2. Создание комментария (только для авторизованных)
@router.post("/videos/{video_id}/comments", response_model=CommentOut)
async def create_comment(video_id: int, comment_data: CommentCreate, current_user: User = Depends(get_current_active_user)):
    async with async_session() as session:
        # Блок begin() сам сделает commit при выходе
        async with session.begin():
            new_comment = Comment(
                text=comment_data.text, 
                video_id=video_id, 
                user_id=current_user.id
            )
            session.add(new_comment)
            # НЕ пишем await session.commit() здесь!
        
        # refresh должен быть ПОСЛЕ закрытия транзакции, чтобы получить id
        await session.refresh(new_comment)
        
    return new_comment

# 3. Удаление комментария (только автор или админ)
@router.delete("/comments/{comment_id}", response_model=None)
async def delete_comment(comment_id: int, current_user: User = Depends(get_current_active_user)):
    async with async_session() as session:
        async with session.begin():
            comment = await session.execute(select(Comment).where(Comment.id == comment_id))
            comment = comment.scalar_one_or_none()
            
            if not comment:
                raise HTTPException(status_code=404, detail="Comment not found")
            if comment.user_id != current_user.id and current_user.role != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
            
            session.delete(comment)
            # НЕ пишем await session.commit() здесь!
            
    return None