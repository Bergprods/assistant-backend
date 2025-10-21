from __future__ import annotations

import sys
from pathlib import Path
import pytest

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncEngine

# Ensure assistant-backend is importable
sys.path.append(str(Path(__file__).resolve().parents[1]))

from repositorys.db import Base, get_async_engine, get_session_maker
from repositorys.crud import CrudRepository


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


@pytest.mark.asyncio
async def test_crud_basic_sqlite(tmp_path):
    # Use a dedicated sqlite file under tmp to ensure fresh schema
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine: AsyncEngine = get_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = get_session_maker(engine)
    repo = CrudRepository(Project)

    # Create
    async with session_maker() as s:
        p = await repo.create(s, {"name": "Default"})
        await s.commit()
        assert p.id is not None

    # Read
    async with session_maker() as s:
        got = await repo.get(s, 1)
        assert got is not None and got.name == "Default"

    # Update
    async with session_maker() as s:
        obj = await repo.get(s, 1)
        assert obj is not None
        await repo.update(s, obj, {"name": "Renamed"})
        await s.commit()

    async with session_maker() as s:
        got2 = await repo.get(s, 1)
        assert got2 is not None and got2.name == "Renamed"

    # List with filter
    async with session_maker() as s:
        rows = await repo.list(s, filters={Project.name: "Renamed"})
        assert len(rows) == 1 and rows[0].name == "Renamed"

    # Delete
    async with session_maker() as s:
        obj = await repo.get(s, 1)
        assert obj is not None
        await repo.delete(s, obj)
        await s.commit()

    async with session_maker() as s:
        gone = await repo.get(s, 1)
        assert gone is None
