# app/main.py
import os
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.routers import auth, videos, comments
from app.database import engine, async_session
from app.models import User, Video

app = FastAPI(title="YouTube MVP")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
# Если в auth.py уже есть prefix="/auth", то здесь его быть не должно!
app.include_router(auth.router) 
app.include_router(videos.router)
app.include_router(comments.router)

# --- СТРАНИЦЫ ---

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    # Получаем список видео из БД для отображения на главной
    async with async_session() as session:
        result = await session.execute(select(Video).where(Video.is_private == False).order_by(Video.id.desc()))
        videos = result.scalars().all()
    
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={
            "is_authenticated": False, 
            "videos": videos # Передаем видео в шаблон
        }
    )

@app.get("/video", response_class=HTMLResponse)
async def read_video(request: Request, id: int):
    # Получаем конкретное видео
    async with async_session() as session:
        result = await session.execute(select(Video).where(Video.id == id))
        video = result.scalar_one_or_none()
    
    return templates.TemplateResponse(
        request=request, 
        name="video.html", 
        context={
            "video_id": id, 
            "video": video,
            "is_authenticated": False
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"is_authenticated": False}
    )

@app.get("/search", response_class=HTMLResponse)
async def read_search(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="search.html", 
        context={"is_authenticated": False}
    )


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()