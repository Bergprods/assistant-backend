"""Stub orchestrator for testing without full AI setup."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


class StubOrchestrator:
    """Minimal orchestrator that returns hardcoded responses for testing."""
    
    def list_services(self) -> Dict[str, str]:
        """Return empty services dict."""
        return {}
    
    def reset(self) -> None:
        """Reset any internal state (no-op for stub)."""
        return None
    
    async def interpret(self, message: str, services: Dict[str, str] | None = None, *, messages: list[dict] | None = None) -> Dict[str, Any]:
        """Return a stub response."""
        return {
            "intents": [],
            "directResponse": f"Echo: {message}",
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "originalMessage": message,
            }
        }
    
    async def dispatch(self, intents: list[Dict[str, Any]]) -> None:
        """Stub dispatch - does nothing."""
        pass
