from __future__ import annotations

import sys
from pathlib import Path

import pytest
import fakeredis.aioredis as fakeredis

sys.path.append(str(Path(__file__).resolve().parents[1]))

import repositorys.redis_work_memory as redis_mod
from repositorys.redis_work_memory import RedisWorkMemory, _key


@pytest.mark.asyncio
async def test_add_and_get_recent_preserves_order_and_ttl():
    fake = fakeredis.FakeRedis(decode_responses=True)
    repo = RedisWorkMemory(url="redis://test")
    repo._r = fake

    await repo.add("session", "user", "hello")
    await repo.add("session", "assistant", "world", extra={"intents": ["x"]})

    history = await repo.get_recent("session")
    assert [entry["role"] for entry in history] == ["user", "assistant"]
    assert history[1]["intents"] == ["x"]

    ttl = await fake.ttl(_key("session"))
    assert ttl > 0


@pytest.mark.asyncio
async def test_clear_removes_buffer():
    fake = fakeredis.FakeRedis(decode_responses=True)
    repo = RedisWorkMemory(url="redis://test")
    repo._r = fake

    await repo.add("session", "user", "hello")
    await repo.clear("session")

    assert await repo.get_recent("session") == []
    assert await fake.exists(_key("session")) == 0


@pytest.mark.asyncio
async def test_buffer_respects_max_size(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    repo = RedisWorkMemory(url="redis://test")
    repo._r = fake

    monkeypatch.setattr(redis_mod, "BUF", 2)

    for idx in range(3):
        await repo.add("session", "user", f"msg{idx}")

    history = await repo.get_recent("session")
    assert len(history) == 2
    assert [entry["content"] for entry in history] == ["msg1", "msg2"]
