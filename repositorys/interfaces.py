from __future__ import annotations

from typing import Protocol, Any, Dict, List, Optional


class WorkMemoryRepository(Protocol):
    async def add(self, session_id: str, role: str, content: str, extra: Optional[Dict[str, Any]] = None) -> None:
        ...

    async def get_recent(self, session_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        ...

    async def clear(self, session_id: str) -> None:
        ...
