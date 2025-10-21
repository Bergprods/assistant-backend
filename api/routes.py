from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any, Optional, List
import importlib

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from api.dependencies import get_chat_manager, get_db_session
from managers.chat_log_manager import ChatLogManager
from repositorys import RouterMessage as RouterMessageModel, Session as SessionModel, ErrorLog as ErrorLogModel

chatlog_manager = ChatLogManager()
logger = logging.getLogger(__name__)

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
    intents: List[Intent]
    direct_response: str = Field(alias="directResponse")
    metadata: OrchestrateMetadata

    model_config = ConfigDict(populate_by_name=True)


class BackendChatResponse(BaseModel):
    orchestrator: OrchestrateResponse
    memory: list[dict[str, Any]] = Field(default_factory=list)


# Try to override stubs with real classes if available at runtime
_mod = None
try:
    _mod = importlib.import_module("my_ai_assistant.api.backend_api")
except ModuleNotFoundError:
    logger.warning("my_ai_assistant.api.backend_api missing; using local schema stubs")
if _mod:
    BackendChatRequest = getattr(_mod, "BackendChatRequest", BackendChatRequest)
    BackendChatResponse = getattr(_mod, "BackendChatResponse", BackendChatResponse)
    Intent = getattr(_mod, "Intent", Intent)
    OrchestrateMetadata = getattr(_mod, "OrchestrateMetadata", OrchestrateMetadata)
    OrchestrateResponse = getattr(_mod, "OrchestrateResponse", OrchestrateResponse)

router = APIRouter(prefix="/api/orchestrator")
def _resolve_chat_manager():
    # Resolve on each request so tests can monkeypatch api.dependencies.get_chat_manager
    from api.dependencies import get_chat_manager as _gm
    return _gm()



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
    return OrchestrateResponse(intents=intents, direct_response=direct, metadata=metadata)


@router.post("/chat", response_model=BackendChatResponse)
async def chat(req: BackendChatRequest, manager = Depends(_resolve_chat_manager)) -> BackendChatResponse:
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
    manager = Depends(_resolve_chat_manager),
):
    """Return recent chat history for the given session without sending a new message."""
    if manager is None:
        return []
    session_id = sessionId or "default"
    history = await manager.get_history(session_id=session_id, limit=limit)
    return history


@router.post("/log")
async def ingest_full_message(payload: dict, db = Depends(get_db_session)):
    """Ingest a full router message JSON and persist across tables, returns ids."""
    res = await chatlog_manager.create_full_message(db, payload)
    return res


@router.get("/log/{sessionId}")
async def get_full_message(sessionId: str, includeOriginal: bool = Query(default=False), db = Depends(get_db_session)):
    """Return the latest full message for a session (sanitized)."""
    res = await chatlog_manager.get_full_message(db, sessionId, include_original=includeOriginal)
    if not res:
        raise HTTPException(404, "No message for session")
    return res


@router.get("/router_messages/{sessionId}")
async def list_router_messages(
    sessionId: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    since: Optional[str] = Query(default=None, description="ISO timestamp to filter createdAt > since"),
    db = Depends(get_db_session),
):
    from sqlalchemy import select, desc
    from datetime import datetime
    # Resolve session row
    res = await db.execute(select(SessionModel).where(SessionModel.session_id == sessionId))
    session_row = res.scalars().first()
    if not session_row:
        return []
    q = select(RouterMessageModel).where(RouterMessageModel.session_id_fk == session_row.id)
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            from sqlalchemy import and_
            q = q.where(RouterMessageModel.created_at > since_dt)
        except Exception:
            pass
    q = q.order_by(desc(RouterMessageModel.created_at)).offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "sessionId": sessionId,
            "sourceMessageId": r.source_message_id,
            "schemaVersion": r.schema_version,
            "language": r.language,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/errors/{sessionId}")
async def list_errors(
    sessionId: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    details: bool = Query(default=False, description="Include error payload details"),
    db = Depends(get_db_session),
):
    from sqlalchemy import select, desc
    res = await db.execute(select(SessionModel).where(SessionModel.session_id == sessionId))
    session_row = res.scalars().first()
    if not session_row:
        return []

    q = (
        select(ErrorLogModel)
        .where(ErrorLogModel.session_id_fk == session_row.id)
        .order_by(desc(ErrorLogModel.created_at))
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()
    # Sanitize payload by omitting it or only providing a small snippet
    out = []
    for e in rows:
        item = {
            "id": e.id,
            "message": e.message,
            "createdAt": e.created_at.isoformat() if e.created_at else None,
        }
        if details:
            item["payload"] = e.payload
        out.append(item)
    return out
