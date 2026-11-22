from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()  # ЕДИНСТВЕННЫЙ Base проекта


async def get_db():
    async with async_session() as session:
        yield session