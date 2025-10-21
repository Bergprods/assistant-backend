from __future__ import annotations

import asyncio

import sys
from pathlib import Path

# Ensure the assistant-backend folder is importable so `data` package resolves
HERE = Path(__file__).resolve()
BACKEND_ROOT = HERE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data.context import get_async_engine
from data.models import Base


async def main():
    use_env = any(arg in ("--env", "-e") for arg in sys.argv[1:])
    engine = get_async_engine(None if use_env else "sqlite+aiosqlite:///./local.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database initialized.")


if __name__ == "__main__":
    asyncio.run(main())
