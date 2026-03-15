"""Generic CRUD base repository with keyset/cursor pagination."""

from __future__ import annotations

import uuid
from typing import Any, Generic, Sequence, Type, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: AsyncSession, model: Type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelT | None:
        return await self._session.get(self._model, entity_id)

    async def list_paginated(
        self,
        cursor: str | None = None,
        limit: int = 50,
        base_query: Select | None = None,
    ) -> dict[str, Any]:
        """Keyset pagination ordered by created_at DESC (newest first).

        Uses cursor based on id for stable page boundaries.
        Returns dict with keys: items, next_cursor, matching CursorPage shape.
        """
        if base_query is None:
            base_query = select(self._model)

        if cursor:
            try:
                cursor_uuid = uuid.UUID(cursor)
            except (ValueError, AttributeError):
                # Invalid cursor — return empty page
                return {"items": [], "next_cursor": None}
            base_query = base_query.where(self._model.id > cursor_uuid)  # type: ignore[attr-defined]

        # Order by created_at DESC so newest items appear first
        if hasattr(self._model, "created_at"):
            base_query = base_query.order_by(self._model.created_at.desc(), self._model.id)  # type: ignore[attr-defined]
        else:
            base_query = base_query.order_by(self._model.id)  # type: ignore[attr-defined]
        base_query = base_query.limit(limit + 1)

        result = await self._session.execute(base_query)
        items: Sequence[ModelT] = result.scalars().all()

        has_more = len(items) > limit
        page_items = list(items[:limit])
        next_cursor = str(page_items[-1].id) if has_more and page_items else None  # type: ignore[attr-defined]

        return {"items": page_items, "next_cursor": next_cursor}

    async def count(self, base_query: Select | None = None) -> int:
        if base_query is None:
            stmt = select(func.count()).select_from(self._model)
        else:
            stmt = select(func.count()).select_from(base_query.subquery())
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def update(self, entity: ModelT, data: dict[str, Any]) -> ModelT:
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self._session.delete(entity)
        await self._session.flush()
