from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _infer_db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return "sqlite+aiosqlite:///./local.db"


def get_async_engine(url: Optional[str] = None, echo: bool = False) -> AsyncEngine:
    return create_async_engine(url or _infer_db_url(), echo=echo, future=True)


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
        except:  # noqa: E722
            await session.rollback()
            raise
