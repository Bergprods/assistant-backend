from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from services.ingest_service import OrchestratorIngestService
from repositorys import (
    Session as SessionModel,
    RouterMessage as RouterMessageModel,
    Intent as IntentModel,
    Item as ItemModel,
    Entity as EntityModel,
    Consent as ConsentModel,
    Telemetry as TelemetryModel,
    ErrorLog as ErrorLogModel,
)


class ChatLogManager:
    """Facade for persisting and retrieving full router messages using separated services."""

    def __init__(self) -> None:
        self.ingest = OrchestratorIngestService()

    async def create_full_message(self, db: AsyncSession, payload: dict) -> dict:
        return await self.ingest.ingest(db, payload)

    async def get_full_message(self, db: AsyncSession, session_id: str, *, include_original: bool = False) -> dict | None:
        # Retrieve latest router_message for a session and reconstruct nested structure
        from sqlalchemy import select, desc

        # Find session
        result = await db.execute(select(SessionModel).where(SessionModel.session_id == session_id))
        session_row = result.scalars().first()
        if not session_row:
            return None

        # Latest router_message
        rm_res = await db.execute(
            select(RouterMessageModel).where(RouterMessageModel.session_id_fk == session_row.id).order_by(desc(RouterMessageModel.id)).limit(1)
        )
        router_msg = rm_res.scalars().first()
        if not router_msg:
            return None

        # Collect intents
        intents_res = await db.execute(
            select(IntentModel).where(IntentModel.session_id_fk == session_row.id).order_by(IntentModel.sequence)
        )
        intents_rows = intents_res.scalars().all()

        # Map items by intent
        from collections import defaultdict

        items_res = await db.execute(
            select(ItemModel).where(ItemModel.intent_id_fk.in_([i.id for i in intents_rows]))
        )
        items_rows = items_res.scalars().all()

        ent_res = await db.execute(
            select(EntityModel).where(EntityModel.item_id_fk.in_([it.id for it in items_rows]))
        )
        entities_rows = ent_res.scalars().all()

        entities_by_item = defaultdict(list)
        for e in entities_rows:
            entities_by_item[e.item_id_fk].append({
                "type": e.type,
                "text": e.text,
                "value": e.value,
                "aliases": e.aliases or [],
            })

        items_by_intent = defaultdict(list)
        for it in items_rows:
            items_by_intent[it.intent_id_fk].append({
                "intentId": None,  # omitted in reconstruction
                "executionCorrelationId": it.execution_correlation_id,
                "dependencyIds": it.dependency_ids or [],
                "description": it.description,
                "type": it.type,
                "subject": it.subject,
                "key": it.key,
                "deterministicKey": it.deterministic_key,
                "confidence": it.confidence,
                "agent": it.agent,
                "attributes": it.attributes or {},
                "payload": it.payload or {},
                "entities": entities_by_item.get(it.id, []),
                "tags": it.tags or [],
                "language": it.language,
                "piiFlags": it.pii_flags or [],
                "redaction": it.redaction,
                "isActionable": it.is_actionable,
                "executionStatus": it.execution_status,
            })

        intents = []
        for i in intents_rows:
            intents.append({
                "id": i.intent_key,
                "name": i.name,
                "sequence": i.sequence,
                "agentSchemaVersion": i.agent_schema_version,
                "confidence": i.confidence,
                "slots": i.slots or {},
                "candidates": i.candidates or [],
                "agentCapabilities": i.agent_capabilities or {},
            })

        # Consents
        cons_res = await db.execute(select(ConsentModel).where(ConsentModel.session_id_fk == session_row.id))
        consents_rows = cons_res.scalars().all()
        consents = [{"scope": c.scope, "granted": c.granted} for c in consents_rows]

        # Telemetry
        tel_res = await db.execute(select(TelemetryModel).where(TelemetryModel.session_id_fk == session_row.id))
        telemetry = tel_res.scalars().first()
        telemetry_json = None
        if telemetry:
            telemetry_json = {
                "generator": telemetry.generator,
                "model": telemetry.model or {},
                "promptVersion": telemetry.prompt_version,
                "latencyMs": telemetry.latency_ms,
                "confidencePolicy": telemetry.confidence_policy or {},
                "keyStrategy": telemetry.key_strategy or {},
            }

        # Errors (sanitized)
        err_res = await db.execute(select(ErrorLogModel).where(ErrorLogModel.session_id_fk == session_row.id))
        error_rows = err_res.scalars().all()
        errors = [
            {
                "message": e.message,
                "createdAt": e.created_at.isoformat() if getattr(e, "created_at", None) else None,
            }
            for e in error_rows
        ]

        # Reconstruct top-level
        result = {
            "schemaVersion": router_msg.schema_version,
            "createdUtc": session_row.created_utc.isoformat() if session_row.created_utc else None,
            "terminated": session_row.terminated,
            "sessionId": session_row.session_id,
            "sourceMessageId": router_msg.source_message_id,
            "userId": session_row.user_id,
            "tenantId": session_row.tenant_id,
            "originalMessage": router_msg.original_message if include_original else None,
            "language": session_row.language,
            "intents": intents,
            "items": items_by_intent.get(None, []) if False else [it for sub in items_by_intent.values() for it in sub],
            "errors": errors,
            "consent": consents,
            "telemetry": telemetry_json,
        }
        return result
