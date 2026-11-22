import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: str = Field(..., min_length=8)
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    file_path: str
    owner_id: int
    is_private: bool
    created_at: Optional[str] = None
    likes_count: int = 0

    views: int = 0
    thumbnail_path: Optional[str] = None
    duration: Optional[str] = "0:00"

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_private: Optional[bool] = None

class LikeStatus(BaseModel):
    likes_count: int
    liked_by_me: bool


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    user_email: str
    created_at: Optional[datetime.datetime] = None


class TokenData(BaseModel):
    email: Optional[str] = None


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    created_at: Optional[str] = None   # ← было datetime (обязательное)
    subscribers_count: int = 0
    videos_count: int = 0
    subscribers_count: int = 0
    subscriptions_count: int = 0


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None

class SubscriptionStatus(BaseModel):
    is_subscribed: bool
    subscribers_count: int

class ChannelInfo(BaseModel):
    id: int
    email: str
    subscribers_count: int
    is_subscribed: bool
    is_own_channel: bool