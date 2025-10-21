from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from data.models import Session as SessionModel, RouterMessage as RouterMessageModel
from repository.assistant import Repository


class OrchestratorIngestService:
    """Domain service: persists an orchestrator payload.
    Keeps repositories generic; composes flow here.
    """

    def __init__(self) -> None:
        self.session_repo: Repository[SessionModel] = Repository(SessionModel)
        self.router_repo: Repository[RouterMessageModel] = Repository(RouterMessageModel)

    async def _get_or_create_session(self, db: AsyncSession, session_id: str, payload: Dict[str, Any]) -> SessionModel:
        # Try fetch by unique session_id
        res = await db.execute(select(SessionModel).where(SessionModel.session_id == session_id))
        row = res.scalars().first()
        if row:
            # optionally update metadata
            updates: Dict[str, Any] = {}
            for k, col in ("userId", SessionModel.user_id), ("tenantId", SessionModel.tenant_id), ("language", SessionModel.language):
                val = payload.get(k)
                if val is not None:
                    updates[col.key] = val  # type: ignore[attr-defined]
            if updates:
                for k, v in updates.items():
                    setattr(row, k, v)
                db.add(row)
                await db.flush()
            return row
        # create new
        return await self.session_repo.create(db, {
            "session_id": session_id,
            "user_id": payload.get("userId"),
            "tenant_id": payload.get("tenantId"),
            "language": payload.get("language"),
        })

    async def ingest(self, db: AsyncSession, payload: Dict[str, Any]) -> Dict[str, int]:
        session_id = payload.get("sessionId") or "default"
        session_row = await self._get_or_create_session(db, session_id, payload)

        router_row = await self.router_repo.create(db, {
            "session_id_fk": session_row.id,
            "source_message_id": payload.get("sourceMessageId"),
            "schema_version": payload.get("schemaVersion"),
            "original_message": payload.get("originalMessage"),
            "language": payload.get("language"),
            "direct_response": payload.get("direct_response") or payload.get("directResponse") or payload.get("directMessage"),
            "message_analysis": payload.get("message_analysis") or payload.get("messageAnalysis"),
            "raw": payload,
        })

        return {"session_db_id": session_row.id, "router_message_id": router_row.id}
