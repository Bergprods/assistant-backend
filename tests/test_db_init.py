from __future__ import annotations

import pytest

from data.context import get_async_engine
from data.models import Base


@pytest.mark.asyncio
async def test_create_all_tables_sqlite_memory():
    engine = get_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # If no exception raised, consider PASS
    assert True
