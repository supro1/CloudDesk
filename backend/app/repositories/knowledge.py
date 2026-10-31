from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Incident, SupportArticle
from backend.app.repositories.base import BaseRepository
from backend.app.schemas.common import TicketCategory


class SupportArticleRepository(BaseRepository[SupportArticle]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SupportArticle)

    async def get_by_slug(self, slug: str) -> SupportArticle | None:
        statement = select(SupportArticle).where(SupportArticle.slug == slug)
        return await self.session.scalar(statement)

    async def list_published(
        self, *, category: TicketCategory | None = None, limit: int = 100, offset: int = 0
    ) -> list[SupportArticle]:
        self._validate_pagination(limit, offset)
        statement = select(SupportArticle).where(SupportArticle.is_published.is_(True))
        if category is not None:
            statement = statement.where(SupportArticle.category == category)
        statement = (
            statement.order_by(SupportArticle.title)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class IncidentRepository(BaseRepository[Incident]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Incident)

    async def list_active(self) -> list[Incident]:
        statement = (
            select(Incident)
            .where(Incident.status == "active")
            .order_by(Incident.started_at.desc(), Incident.created_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())
