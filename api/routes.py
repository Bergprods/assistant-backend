from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_chat_manager
logger = logging.getLogger(__name__)

try:
    from my_ai_assistant.api.backend_api import (
        BackendChatRequest,
        BackendChatResponse,
        Intent,
        OrchestrateMetadata,
        OrchestrateResponse,
    )
except ModuleNotFoundError:
    logger.warning("my_ai_assistant.api.backend_api missing; using local schema stubs")

    class BackendChatRequest(BaseModel):
        message: str
        sessionId: Optional[str] = None
        waitFor: Optional[float] = None
        historyLimit: Optional[int] = None

        class Config:
            allow_population_by_field_name = True

        @property
        def session_id(self) -> str:
            return self.sessionId or "default"

        @property
        def wait_for(self) -> Optional[float]:
            return self.waitFor

        @property
        def history_limit(self) -> Optional[int]:
            return self.historyLimit

    class Intent(BaseModel):
        domain: str
        requires: list[str] = Field(default_factory=list)

    class OrchestrateMetadata(BaseModel):
        timestamp: str
        originalMessage: str

        class Config:
            extra = "allow"

    class OrchestrateResponse(BaseModel):
        intents: list[Intent]
        directResponse: str
        metadata: OrchestrateMetadata

    class BackendChatResponse(BaseModel):
        orchestrator: OrchestrateResponse
        memory: list[dict[str, Any]] = Field(default_factory=list)

router = APIRouter(prefix="/api/orchestrator")


def _fallback_response(message: str) -> OrchestrateResponse:
    text = message.lower()
    intents: list[Intent] = []
    if any(term in text for term in ("issue", "bug", "create issue", "ticket")):
        intents.append(Intent(domain="github"))
    if any(term in text for term in ("turn on", "turn off", "lights", "switch", "home assistant", "hvac")):
        intents.append(Intent(domain="homeassistant"))

    if not intents:
        direct = "Jag kan inte automatiskt utföra det här. Kan du ge mer information eller omformulera?"
    else:
        direct = "Jag förbereder det du bad om och återkommer när det är klart."

    metadata = OrchestrateMetadata(
        timestamp=datetime.now(timezone.utc).isoformat(),
        originalMessage=message,
    )
    return OrchestrateResponse(intents=intents, directResponse=direct, metadata=metadata)


@router.post("/chat", response_model=BackendChatResponse)
async def chat(req: BackendChatRequest, manager = Depends(get_chat_manager)) -> BackendChatResponse:
    if not req.message:
        raise HTTPException(400, "message required")

    session_id = getattr(req, "session_id", None)
    if session_id is None and hasattr(req, "sessionId"):
        session_id = req.sessionId or "default"
    session_id = session_id or "default"

    if manager is None:
        orchestrator = _fallback_response(req.message)
        return BackendChatResponse(orchestrator=orchestrator, memory=[])

    wait_for = getattr(req, "wait_for", None)
    history_limit = getattr(req, "history_limit", None)

    result = await manager.handle_message(
        req.message,
        session_id=session_id,
        wait_for=wait_for,
        history_limit=history_limit,
    )

    orchestrator_payload = result.get("orchestrator", {})
    memory_payload = result.get("memory", [])

    orchestrator = orchestrator_payload if isinstance(orchestrator_payload, OrchestrateResponse) else OrchestrateResponse(**orchestrator_payload)
    return BackendChatResponse(orchestrator=orchestrator, memory=memory_payload)


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/assistant_status")
async def assistant_status():
    openai_key_present = bool(os.getenv("OPENAI_API_KEY"))
    return {"wired": openai_key_present, "openai_key_present": openai_key_present}


@router.get("/history")
async def get_history(
    sessionId: Optional[str] = Query(default="default"),
    limit: Optional[int] = Query(default=12),
    manager = Depends(get_chat_manager),
):
    """Return recent chat history for the given session without sending a new message."""
    if manager is None:
        return []
    session_id = sessionId or "default"
    history = await manager.get_history(session_id=session_id, limit=limit)
    return history
