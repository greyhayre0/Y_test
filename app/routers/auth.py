# app/routers/auth.py
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app import config
from app.database import async_session
from app.models import User
from app.schemas import UserCreate, UserOut, Token
from app.auth import ACCESS_TOKEN_EXPIRE_MINUTES, get_password_hash, create_access_token, get_current_user, get_current_active_user, verify_password

# ВАЖНО: Добавлен префикс /auth
router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=UserOut)
async def register_user(form_data: UserCreate):
    async with async_session() as session:
        # Блок begin() автоматически сделает commit при выходе
        async with session.begin():
            user = await session.execute(select(User).where(User.email == form_data.email))
            user = user.scalar_one_or_none()
            if user:
                raise HTTPException(status_code=400, detail="Email already registered")
            
            hashed_password = get_password_hash(form_data.password)
            new_user = User(email=form_data.email, hashed_password=hashed_password)
            session.add(new_user)
            # НЕ пишем await session.commit() здесь! Блок begin() сделает это сам.
        
        # refresh должен быть ПОСЛЕ закрытия транзакции, чтобы получить id
        await session.refresh(new_user)
        
    return new_user

@router.post("/login", response_model=Token)
async def login_user(form_data: OAuth2PasswordRequestForm = Depends()):
    async with async_session() as session:
        async with session.begin():
            user = await session.execute(select(User).where(User.email == form_data.username))
            user = user.scalar_one_or_none()
            if not user or not verify_password(form_data.password, user.hashed_password):
                raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    # Генерация токена вне транзакции
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}