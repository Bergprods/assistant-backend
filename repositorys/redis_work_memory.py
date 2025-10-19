from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from .interfaces import WorkMemoryRepository


BUF = int(os.getenv("CHAT_BUFFER_SIZE", "12"))
TTL = int(os.getenv("CHAT_BUFFER_TTL", "3600"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


def _key(session_id: str) -> str:
    return f"chat:{session_id}:buffer"


class RedisWorkMemory(WorkMemoryRepository):
    def __init__(self, url: str = REDIS_URL):
        self._r = redis.from_url(url, decode_responses=True)

    async def add(self, session_id: str, role: str, content: str, extra: Optional[Dict[str, Any]] = None) -> None:
        item: Dict[str, Any] = {"t": int(time.time()), "role": role, "content": content}
        if extra:
            item.update(extra)
        payload = json.dumps(item, ensure_ascii=False)
        k = _key(session_id)
        pipe = self._r.pipeline()
        pipe.lpush(k, payload).ltrim(k, 0, BUF - 1).expire(k, TTL)
        await pipe.execute()

    async def get_recent(self, session_id: str, limit: int = BUF) -> List[Dict[str, Any]]:
        rows = await self._r.lrange(_key(session_id), 0, max(0, limit) - 1)
        out: List[Dict[str, Any]] = []
        for raw in reversed(rows):
            try:
                out.append(json.loads(raw))
            except Exception:
                # skip malformed rows
                pass
        return out

    async def clear(self, session_id: str) -> None:
        await self._r.delete(_key(session_id))
