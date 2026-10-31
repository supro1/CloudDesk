from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.ext.asyncio import create_async_engine as sqlalchemy_create_async_engine

from backend.app.core.config import get_settings
from backend.app.models.entities import Base


def create_database_engine(database_url: str | None = None) -> AsyncEngine:
    url = database_url or get_settings().database_url
    parsed_url = make_url(url)
    if parsed_url.get_backend_name() == "sqlite" and parsed_url.database not in (
        None,
        "",
        ":memory:",
    ):
        Path(parsed_url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return sqlalchemy_create_async_engine(url, pool_pre_ping=True)


engine = create_database_engine()
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def create_tables(target_engine: AsyncEngine | None = None) -> None:
    async with (target_engine or engine).begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    await engine.dispose()
