from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient
from app import app


class FakeRepo:
    def __init__(self) -> None:
        self._data: Dict[str, List[Dict[str, Any]]] = {}

    async def add(self, session_id: str, role: str, content: str, extra: Optional[Dict[str, Any]] = None) -> None:
        from time import time
        item: Dict[str, Any] = {"t": int(time()), "role": role, "content": content}
        if extra:
            item.update(extra)
        self._data.setdefault(session_id, []).append(item)

    async def get_recent(self, session_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        rows = self._data.get(session_id, [])
        return rows[-limit:]

    async def clear(self, session_id: str) -> None:
        self._data.pop(session_id, None)
def test_chat_flow_end_to_end(monkeypatch):
    # Wire a ChatManager with StubOrchestrator and in-memory repo
    from managers.stub_orchestrator import StubOrchestrator
    from managers.chat_manager import ChatManager
    from services.work_memory_service import WorkMemoryService

    repo = FakeRepo()
    memory = WorkMemoryService(repo)  # type: ignore[arg-type]
    orch = StubOrchestrator()
    manager = ChatManager(orch, memory)

    # Patch dependency getter so routes use our manager
    import api.dependencies as deps

    def _get_chat_manager_override():
        return manager

    monkeypatch.setattr(deps, "get_chat_manager", _get_chat_manager_override)

    session_id = "e2e-test"
    with TestClient(app) as client:
        # Initially, history should be empty
        r = client.get("/api/orchestrator/history", params={"sessionId": session_id, "limit": 12})
        assert r.status_code == 200
        hist = r.json()
        assert isinstance(hist, list) and len(hist) == 0

        # Send a chat message
        payload = {"message": "Hej där", "sessionId": session_id}
        r2 = client.post("/api/orchestrator/chat", content=json.dumps(payload))
        assert r2.status_code == 200
        body = r2.json()
        assert "orchestrator" in body and "memory" in body
        orch_payload = body["orchestrator"]
        assert isinstance(orch_payload.get("directResponse", ""), str)
        assert isinstance(orch_payload.get("intents", []), list)
        # The memory returned should include the user and assistant entries
        mem = body["memory"]
        assert len(mem) >= 2
        roles = [m.get("role") for m in mem]
        assert "user" in roles and "assistant" in roles

        # History endpoint should now return the same memory
        r3 = client.get("/api/orchestrator/history", params={"sessionId": session_id, "limit": 12})
        assert r3.status_code == 200
        hist2 = r3.json()
        assert len(hist2) == len(mem)
        assert hist2[-1]["role"] == mem[-1]["role"]
