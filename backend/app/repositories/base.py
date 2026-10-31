from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Base


class BaseRepository[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

    async def get(self, record_id: str) -> ModelT | None:
        return await self.session.get(self.model, record_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        self._validate_pagination(limit, offset)

        statement = (
            select(self.model)
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def count(self) -> int:
        statement = select(func.count()).select_from(self.model)
        return await self.session.scalar(statement) or 0

    async def create(self, **values: Any) -> ModelT:
        record = self.model(**values)
        self.session.add(record)
        await self.session.flush()
        return record

    async def update(self, record_id: str, values: Mapping[str, Any]) -> ModelT | None:
        columns = {column.key for column in self.model.__table__.columns}
        protected_columns = {"id", "created_at", "updated_at"}
        invalid_columns = (set(values) - columns) | (set(values) & protected_columns)
        if invalid_columns:
            names = ", ".join(sorted(invalid_columns))
            raise ValueError(f"Cannot update repository fields: {names}")

        record = await self.get(record_id)
        if record is None:
            return None

        for name, value in values.items():
            setattr(record, name, value)
        await self.session.flush()
        return record

    async def delete(self, record_id: str) -> bool:
        record = await self.get(record_id)
        if record is None:
            return False
        await self.session.delete(record)
        await self.session.flush()
        return True
