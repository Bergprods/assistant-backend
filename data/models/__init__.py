from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..context import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=_uuid_str)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    terminated: Mapped[bool] = mapped_column(Boolean, server_default=text("0"), nullable=False)
    created_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=func.now())

    router_messages: Mapped[list["RouterMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    intents: Mapped[list["Intent"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    consents: Mapped[list["Consent"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    telemetry: Mapped[Telemetry | None] = relationship(back_populates="session", cascade="all, delete-orphan", uselist=False)
    errors: Mapped[list["ErrorLog"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class RouterMessage(Base):
    __tablename__ = "router_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id_fk: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_uuid_str)
    source_message_id: Mapped[str | None] = mapped_column(String(128))
    schema_version: Mapped[str | None] = mapped_column(String(32))
    original_message: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(32))
    direct_response: Mapped[str | None] = mapped_column(Text)
    message_analysis: Mapped[dict | None] = mapped_column(JSON)
    raw: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    session: Mapped[Session] = relationship(back_populates="router_messages")


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=_uuid_str)
    session_id_fk: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    intent_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(64))
    sequence: Mapped[int | None] = mapped_column(Integer)
    agent_schema_version: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)
    slots: Mapped[dict | None] = mapped_column(JSON)
    candidates: Mapped[list | None] = mapped_column(JSON)
    agent_capabilities: Mapped[dict | None] = mapped_column(JSON)

    session: Mapped[Session] = relationship(back_populates="intents")
    items: Mapped[list["Item"]] = relationship(back_populates="intent", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_id_fk: Mapped[int] = mapped_column(ForeignKey("intents.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_correlation_id: Mapped[str | None] = mapped_column(String(128))
    dependency_ids: Mapped[list | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(String(64))
    subject: Mapped[str | None] = mapped_column(String(64))
    key: Mapped[str | None] = mapped_column(String(256))
    deterministic_key: Mapped[str | None] = mapped_column(String(256))
    confidence: Mapped[float | None] = mapped_column(Float)
    agent: Mapped[str | None] = mapped_column(String(64))
    attributes: Mapped[dict | None] = mapped_column(JSON)
    payload: Mapped[dict | None] = mapped_column(JSON)
    tags: Mapped[list | None] = mapped_column(JSON)
    language: Mapped[str | None] = mapped_column(String(32))
    pii_flags: Mapped[list | None] = mapped_column(JSON)
    redaction: Mapped[str | None] = mapped_column(String(32))
    is_actionable: Mapped[bool | None] = mapped_column(Boolean)
    execution_status: Mapped[str | None] = mapped_column(String(32))

    intent: Mapped[Intent] = relationship(back_populates="items")
    entities: Mapped[list["Entity"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id_fk: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str | None] = mapped_column(Text)
    value: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list | None] = mapped_column(JSON)

    item: Mapped[Item] = relationship(back_populates="entities")


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id_fk: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(128), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, server_default=text("0"), nullable=False)

    session: Mapped[Session] = relationship(back_populates="consents")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id_fk: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    generator: Mapped[str | None] = mapped_column(String(128))
    model: Mapped[dict | None] = mapped_column(JSON)
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    confidence_policy: Mapped[dict | None] = mapped_column(JSON)
    key_strategy: Mapped[dict | None] = mapped_column(JSON)

    session: Mapped[Session] = relationship(back_populates="telemetry")


class ErrorLog(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id_fk: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    session: Mapped[Session] = relationship(back_populates="errors")


__all__ = [
    "Session",
    "RouterMessage",
    "Intent",
    "Item",
    "Entity",
    "Consent",
    "Telemetry",
    "ErrorLog",
]
