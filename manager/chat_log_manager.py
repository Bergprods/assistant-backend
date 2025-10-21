from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.assistant_core.ingest_service import OrchestratorIngestService
from data.models import Session as SessionModel, RouterMessage as RouterMessageModel


class ChatLogManager:
    """Facade for persisting and retrieving router messages via services."""

    def __init__(self) -> None:
        self.ingest = OrchestratorIngestService()

    async def create_full_message(self, db: AsyncSession, payload: dict) -> dict:
        return await self.ingest.ingest(db, payload)

    async def get_full_message(self, db: AsyncSession, session_id: str, *, include_original: bool = False) -> dict | None:
        # find session
        res = await db.execute(select(SessionModel).where(SessionModel.session_id == session_id))
        session_row = res.scalars().first()
        if not session_row:
            return None
        # latest router message
        rm_res = await db.execute(
            select(RouterMessageModel)
            .where(RouterMessageModel.session_id_fk == session_row.id)
            .order_by(desc(RouterMessageModel.id))
            .limit(1)
        )
        router_msg = rm_res.scalars().first()
        if not router_msg:
            return None
        # Compose minimal structure; can be expanded later by services
        return {
            "schemaVersion": router_msg.schema_version,
            "createdUtc": session_row.created_utc.isoformat() if session_row.created_utc else None,
            "terminated": session_row.terminated,
            "sessionId": session_row.session_id,
            "sourceMessageId": router_msg.source_message_id,
            "userId": session_row.user_id,
            "tenantId": session_row.tenant_id,
            "originalMessage": router_msg.original_message if include_original else None,
            "language": session_row.language,
            "intents": [],
            "items": [],
            "errors": [],
            "consent": [],
            "telemetry": None,
        }
