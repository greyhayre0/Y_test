# app/main.py
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.routers import auth, videos, comments, profile, subscriptions
from app.database import Base, engine, async_session
from app.models import User, Video  # импорт модуля регистрирует ВСЕ модели в Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём недостающие таблицы при старте (для разработки; для продакшена — Alembic).
    # Существующие таблицы и данные не трогаются.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="YouTube MVP", lifespan=lifespan)

# CORS: страница и API на одном origin, так что он почти не нужен.
# "*" вместе с allow_credentials=True — некорректная комбинация, указываем явно.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# Шаблонизатор
templates = Jinja2Templates(directory="frontend")

# --- API ---
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(comments.router)
app.include_router(profile.router)
app.include_router(subscriptions.router)


# --- СТРАНИЦЫ ---

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    async with async_session() as session:
        result = await session.execute(
            select(Video).where(Video.is_private == False).order_by(Video.id.desc())
        )
        videos_list = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"is_authenticated": False, "videos": videos_list},
    )


@app.get("/video", response_class=HTMLResponse)
async def read_video(request: Request, id: int):
    async with async_session() as session:
        result = await session.execute(select(Video).where(Video.id == id))
        video = result.scalar_one_or_none()

    if video is None:
        return HTMLResponse("Видео не найдено", status_code=404)

    return templates.TemplateResponse(
        request=request,
        name="video.html",
        context={"video_id": id, "video": video, "is_authenticated": False},
    )


@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse(
        request=request, name="login.html", context={"is_authenticated": False}
    )


@app.get("/search", response_class=HTMLResponse)
async def read_search(request: Request):
    return templates.TemplateResponse(
        request=request, name="search.html", context={"is_authenticated": False}
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="profile.html", context={"is_authenticated": False}
    )

@app.get("/profile/{user_id}", response_class=HTMLResponse)
async def public_profile(request: Request, user_id: int):
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={"is_authenticated": False, "profile_user_id": user_id},
    )