from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _normalize_db_url(url: str | None) -> str:
    if not url:
        return "sqlite+aiosqlite:///./local.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[1]:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_async_engine(url: Optional[str] = None, *, echo: bool = False) -> AsyncEngine:
    resolved = _normalize_db_url(url or os.getenv("DATABASE_URL"))
    return create_async_engine(resolved, echo=echo, future=True)


def get_session_maker(engine: Optional[AsyncEngine] = None) -> async_sessionmaker[AsyncSession]:
    eng = engine or get_async_engine()
    return async_sessionmaker(eng, expire_on_commit=False)


@asynccontextmanager
async def lifespan_session(session_maker: Optional[async_sessionmaker[AsyncSession]] = None) -> AsyncGenerator[AsyncSession, None]:
    sm = session_maker or get_session_maker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
