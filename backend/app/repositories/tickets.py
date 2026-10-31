from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Ticket, TicketMessage
from backend.app.repositories.base import BaseRepository


class TicketRepository(BaseRepository[Ticket]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Ticket)

    async def get_by_ticket_number(self, ticket_number: str) -> Ticket | None:
        statement = select(Ticket).where(Ticket.ticket_number == ticket_number)
        return await self.session.scalar(statement)

    async def get_by_external_id(self, channel: str, external_id: str) -> Ticket | None:
        statement = select(Ticket).where(
            Ticket.channel == channel,
            Ticket.external_id == external_id,
        )
        return await self.session.scalar(statement)

    async def list_for_customer(
        self, customer_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[Ticket]:
        self._validate_pagination(limit, offset)
        statement = (
            select(Ticket)
            .where(Ticket.customer_id == customer_id)
            .order_by(Ticket.created_at.desc(), Ticket.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_by_status(
        self, status: str, *, limit: int = 100, offset: int = 0
    ) -> list[Ticket]:
        self._validate_pagination(limit, offset)
        statement = (
            select(Ticket)
            .where(Ticket.status == status)
            .order_by(Ticket.created_at.desc(), Ticket.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class TicketMessageRepository(BaseRepository[TicketMessage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TicketMessage)

    async def list_for_ticket(self, ticket_id: str) -> list[TicketMessage]:
        statement = (
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at, TicketMessage.id)
        )
        result = await self.session.scalars(statement)
        return list(result.all())
