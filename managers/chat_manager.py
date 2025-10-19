from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from services.work_memory_service import WorkMemoryService


class OrchestratorLike(Protocol):
    async def interpret(self, original: str, services: Dict[str, str], messages: Optional[list] = None) -> Dict[str, Any]: ...

    def list_services(self) -> Dict[str, str]: ...

    async def dispatch(
        self,
        original: str,
        services: Optional[List[str]] = None,
        wait_for: Optional[float] = None,
    ) -> Dict[str, Any]: ...


class ChatManager:
    def __init__(self, orchestrator: OrchestratorLike, memory: WorkMemoryService):
        self.orchestrator = orchestrator
        self.memory = memory

    async def get_history(self, session_id: str = "default", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return recent chat history for a session without adding a new message."""
        return await self.memory.recent(session_id, limit=limit or 12)

    async def handle_message(
        self,
        message: str,
        *,
        session_id: str = "default",
        wait_for: Optional[float] = None,
        history_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        # store user message
        await self.memory.append_user(session_id, message)

        # Hämta hela historiken (utan limit) för att skicka till orchestratorn
        full_history = await self.memory.recent(session_id, limit=100)

        # Skapa OpenAI-format av historiken
        messages = []
        for entry in full_history:
            if entry["role"] in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})
        # Lägg till senaste user-meddelandet om det inte redan är med
        if not messages or messages[-1]["role"] != "user":
            messages.append({"role": "user", "content": message})

        # interpret och skicka med historik
        result = await self.orchestrator.interpret(message, self.orchestrator.list_services(), messages=messages)

        # store assistant reply
        await self.memory.append_assistant(
            session_id,
            result.get("directResponse", ""),
            intents=result.get("intents"),
        )

        # non-blocking dispatch if requested
        if wait_for is None:
            try:
                import asyncio
                asyncio.create_task(
                    self.orchestrator.dispatch(
                        message,
                        services=[i.get("domain") for i in result.get("intents", []) if isinstance(i, dict) and i.get("domain")],
                        wait_for=None,
                    )
                )
            except Exception:
                pass
        else:
            try:
                await self.orchestrator.dispatch(
                    message,
                    services=[i.get("domain") for i in result.get("intents", []) if isinstance(i, dict) and i.get("domain")],
                    wait_for=wait_for,
                )
            except Exception:
                pass

        history = await self.memory.recent(session_id, limit=history_limit or 12)

        return {
            "orchestrator": result,
            "memory": history,
        }
