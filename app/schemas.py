from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class UserCreate(BaseModel):
    email: str = Field(..., min_length=8)
    password: str = Field(..., min_length=8)

class UserOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: Optional[str] = None  # <-- Добавлено Optional и = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class VideoOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    file_path: str
    owner_id: int
    is_private: bool
    created_at: Optional[str] = None
    likes_count: int = 0
    
    # Поля, которых нет в БД, но они нужны фронтенду
    views: int = 0
    thumbnail_path: Optional[str] = None
    duration: Optional[str] = "0:00"

    model_config = ConfigDict(from_attributes=True)

class LikeStatus(BaseModel):
    likes_count: int
    liked_by_me: bool

class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

class CommentOut(BaseModel):
    id: int
    text: str
    video_id: int
    user_id: int
    user_email: str  # <-- Добавляем поле
    created_at: Optional[str] = None  # <-- ЭТО ГЛАВНОЕ

class TokenData(BaseModel):
    email: Optional[str] = None  # <-- Было username, стало email