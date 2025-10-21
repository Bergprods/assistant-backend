from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app
from repositorys import Base, get_async_engine, get_session_maker


@pytest.fixture(autouse=True)
def setup_sqlite(monkeypatch):
    # Force in-memory sqlite for API tests by patching session maker in dependencies
    from api import dependencies

    engine = get_async_engine("sqlite+aiosqlite:///:memory:")

    async def create_schema():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    import asyncio
    asyncio.get_event_loop().run_until_complete(create_schema())

    session_maker = get_session_maker(engine)
    dependencies._SessionLocal = session_maker
    client = TestClient(app)
    yield


def load_template() -> dict:
    p = Path(__file__).resolve().parents[2] / "assistant-common" / "json-templates" / "router_message.template.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_health_and_status():
    client = TestClient(app)
    r = client.get("/api/orchestrator/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True

    r2 = client.get("/api/orchestrator/assistant_status")
    assert r2.status_code == 200
    assert "wired" in r2.json()


def test_post_and_get_log():
    client = TestClient(app)
    payload = load_template()
    # Create
    r = client.post("/api/orchestrator/log", json=payload)
    assert r.status_code == 200
    ids = r.json()
    assert ids["session_db_id"] > 0
    assert ids["router_message_id"] > 0

    # Get latest full message for session
    session_id = payload["sessionId"]
    g = client.get(f"/api/orchestrator/log/{session_id}")
    assert g.status_code == 200
    data = g.json()
    assert data["sessionId"] == session_id
    assert data["intents"]
    assert data["items"]


def test_list_router_messages_and_errors():
    client = TestClient(app)
    payload = load_template()
    # Ingest two messages for same session
    client.post("/api/orchestrator/log", json=payload)
    client.post("/api/orchestrator/log", json=payload)

    session_id = payload["sessionId"]
    # List router messages
    rm = client.get(f"/api/orchestrator/router_messages/{session_id}")
    assert rm.status_code == 200
    lst = rm.json()
    assert isinstance(lst, list) and len(lst) >= 2
    assert lst[0]["sessionId"] == session_id

    # Errors (none expected in template)
    er = client.get(f"/api/orchestrator/errors/{session_id}")
    assert er.status_code == 200
    errs = er.json()
    assert isinstance(errs, list)

    # Add an error by posting a malformed payload (missing fields)
    bad = {"sessionId": session_id, "telemetry": {"generator": "x"}}
    client.post("/api/orchestrator/log", json=bad)
    er2 = client.get(f"/api/orchestrator/errors/{session_id}?details=true")
    assert er2.status_code == 200
    errs2 = er2.json()
    assert isinstance(errs2, list)