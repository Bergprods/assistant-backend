from __future__ import annotations

from typing import Any, Dict, Generic, Iterable, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class CrudRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    async def create(self, session: AsyncSession, data: Dict[str, Any]) -> T:
        obj = self.model(**data)  # type: ignore[call-arg]
        session.add(obj)
        await session.flush()
        return obj

    async def get(self, session: AsyncSession, id: Any) -> Optional[T]:
        return await session.get(self.model, id)

    async def list(self, session: AsyncSession, *, filters: Optional[Dict[Any, Any]] = None) -> List[T]:
        stmt = select(self.model)
        if filters:
            for col, val in filters.items():
                stmt = stmt.where(col == val)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def update(self, session: AsyncSession, obj: T, data: Dict[str, Any]) -> T:
        for k, v in data.items():
            setattr(obj, k, v)
        session.add(obj)
        await session.flush()
        return obj

    async def delete(self, session: AsyncSession, obj: T) -> None:
        await session.delete(obj)
        
