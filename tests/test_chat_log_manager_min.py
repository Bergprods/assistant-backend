from __future__ import annotations

import pytest

from data.context import get_async_engine, get_session_maker
from data.models import Base
from manager import ChatLogManager


@pytest.mark.asyncio
async def test_ingest_and_get_minimal():
    engine = get_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = get_session_maker(engine)

    mgr = ChatLogManager()
    payload = {
        "sessionId": "test-session",
        "schemaVersion": "v1",
        "sourceMessageId": "src-1",
        "originalMessage": "Hej",
        "language": "sv",
    }
    async with sm() as db:
        ids = await mgr.create_full_message(db, payload)
        assert ids["session_db_id"] > 0 and ids["router_message_id"] > 0
        await db.commit()

    async with sm() as db:
        got = await mgr.get_full_message(db, "test-session", include_original=True)
        assert got is not None
        assert got["sessionId"] == "test-session"
        assert got["originalMessage"] == "Hej"
