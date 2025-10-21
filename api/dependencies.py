from __future__ import annotations

import os
import logging
import importlib
from typing import Optional

from repositorys.redis_work_memory import RedisWorkMemory
from repositorys import get_async_engine, get_session_maker
from contextlib import asynccontextmanager
from services.work_memory_service import WorkMemoryService
from managers.chat_manager import ChatManager
from my_ai_assistant.managers import OrchestratorLike


logger = logging.getLogger(__name__)

_orchestrator: Optional[OrchestratorLike] = None
_cached_manager: dict[str, Optional[ChatManager]] = {"value": None}


def _load_orchestrator_components() -> Optional[tuple[OrchestratorLike, ChatManager]]:
    """Load orchestrator components. Falls back to stub if full AI unavailable."""
    
    # Try full AI setup
    try:
        agent_service_mod = importlib.import_module("my_ai_assistant.services.agent_service")
        orchestrator_mod = importlib.import_module("my_ai_assistant.services.orchestrator_service")
        assistant_mod = importlib.import_module("my_ai_assistant.assistant")
        adapter_mod = importlib.import_module("my_ai_assistant.providers.openai_adapter")
        
        AgentService = getattr(agent_service_mod, "AgentService")
        OrchestratorService = getattr(orchestrator_mod, "OrchestratorService")
        BaseAssistant = getattr(assistant_mod, "BaseAssistant")
        OpenAIAdapter = getattr(adapter_mod, "OpenAIAdapter")

        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            logger.info("OPENAI_API_KEY missing; using stub orchestrator")
            raise ModuleNotFoundError("No API key")

        adapter = OpenAIAdapter(api_key=openai_key)
        assistant = BaseAssistant(adapter)
        agent = AgentService(assistant)
        orch: OrchestratorLike = OrchestratorService(agent)

        try:
            github_mod = importlib.import_module("my_ai_assistant.services.github_service")
            homeassistant_mod = importlib.import_module("my_ai_assistant.services.homeassistant_service")
            smalltalk_mod = importlib.import_module("my_ai_assistant.services.smalltalk_service")

            orch.register("github", github_mod.GitHubService(), description="Create issues/projects in GitHub")
            orch.register("homeassistant", homeassistant_mod.HomeAssistantService(), description="Control Home Assistant devices")
            orch.register("smalltalk", smalltalk_mod.SmallTalkService(), description="Small talk and confirmations")
        except ModuleNotFoundError:
            logger.warning("Optional my_ai_assistant service modules missing; continuing without registrations")

        memory_service = get_work_service()
        manager = ChatManager(orch, memory_service)
        logger.info("Full AI orchestrator loaded")
        return orch, manager
        
    except ModuleNotFoundError as e:
        logger.info(f"Full AI unavailable ({e}); using stub orchestrator for memory testing")
        
        # Use stub orchestrator
        from managers.stub_orchestrator import StubOrchestrator
        orch = StubOrchestrator()
        memory_service = get_work_service()
        manager = ChatManager(orch, memory_service)
        return orch, manager


def get_orchestrator() -> Optional[OrchestratorLike]:
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator
    try:
        loaded = _load_orchestrator_components()
        if loaded is None:
            return None
        orch, manager = loaded
        _orchestrator = orch
        _cached_manager["value"] = manager
        return _orchestrator
    except Exception:
        logger.exception("Failed to initialize orchestrator")
        return None


def get_work_repo() -> RedisWorkMemory:
    return RedisWorkMemory()


def get_work_service() -> WorkMemoryService:
    return WorkMemoryService(get_work_repo())


def get_chat_manager() -> ChatManager | None:
    """Get or create ChatManager. Returns None if orchestrator unavailable."""
    cached = _cached_manager.get("value")
    if cached:
        return cached
    
    # Try loading full orchestrator
    loaded = _load_orchestrator_components()
    if loaded is not None:
        orch, manager = loaded
        _orchestrator = orch
        _cached_manager["value"] = manager
        return manager
    
    # If orchestrator unavailable, return None
    logger.info("ChatManager unavailable; orchestrator components not loaded")
    return None


_engine = None
_SessionLocal = None

def _normalize_db_url(url: str | None) -> str | None:
    if not url:
        return url
    # ensure async driver for postgres
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+" not in url.split("://", 1)[1]:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

def _ensure_db():
    global _engine, _SessionLocal
    if _SessionLocal is not None:
        return
    import os
    url = _normalize_db_url(os.getenv("DATABASE_URL"))
    _engine = get_async_engine(url)
    _SessionLocal = get_session_maker(_engine)

async def get_db_session():
    if _SessionLocal is None:
        _ensure_db()
    async with _SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except:  # noqa: E722
            await session.rollback()
            raise
