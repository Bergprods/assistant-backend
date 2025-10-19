from __future__ import annotations

from typing import Any, Dict, List

from repositorys.interfaces import WorkMemoryRepository


class WorkMemoryService:
    def __init__(self, repo: WorkMemoryRepository):
        self.repo = repo

    async def append_user(self, session_id: str, message: str) -> None:
        await self.repo.add(session_id, role="user", content=message)

    async def append_assistant(self, session_id: str, message: str, *, intents: List[Dict[str, Any]] | None = None) -> None:
        extra: Dict[str, Any] = {}
        if intents:
            extra["intents"] = intents
        await self.repo.add(session_id, role="assistant", content=message, extra=extra)

    async def recent(self, session_id: str, limit: int | None = 12) -> List[Dict[str, Any]]:
        lim = limit if limit is not None else 12
        return await self.repo.get_recent(session_id, limit=lim)

    async def clear(self, session_id: str) -> None:
        await self.repo.clear(session_id)
