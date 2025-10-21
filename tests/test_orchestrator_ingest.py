import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from repositorys import Base, get_async_engine, get_session_maker
from services.ingest_service import OrchestratorIngestService


@pytest.mark.asyncio
async def test_ingest_router_message(tmp_path: Path):
    # Use SQLite for tests
    engine: AsyncEngine = get_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sm = get_session_maker(engine)
    ingest = OrchestratorIngestService()

    # Load sample payload
    template_path = Path(__file__).resolve().parents[2] / "assistant-common" / "json-templates" / "router_message.template.json"
    data = json.loads(template_path.read_text(encoding="utf-8"))

    async with sm() as session:
        res = await ingest.ingest(session, data)
        await session.commit()
        assert res["session_db_id"] > 0
        assert res["router_message_id"] > 0

    # Quick row counts
    async with engine.connect() as conn:
        r1 = await conn.execute(text("select count(*) from sessions"))
        r2 = await conn.execute(text("select count(*) from router_messages"))
        r3 = await conn.execute(text("select count(*) from intents"))
        r4 = await conn.execute(text("select count(*) from items"))
        r5 = await conn.execute(text("select count(*) from entities"))
        r6 = await conn.execute(text("select count(*) from consents"))
        r7 = await conn.execute(text("select count(*) from telemetry"))
        assert r1.scalar_one() == 1
        assert r2.scalar_one() == 1
        assert r3.scalar_one() >= 2
        assert r4.scalar_one() >= 2
        assert r5.scalar_one() >= 3
        assert r6.scalar_one() >= 1
        assert r7.scalar_one() == 1
