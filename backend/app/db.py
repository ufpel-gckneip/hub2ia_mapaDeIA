"""Database engine, session factory, and declarative Base."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# Async engine for the FastAPI app. psycopg3 supports async natively via
# the "postgresql+psycopg://" URL (no separate asyncpg driver needed).
engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
