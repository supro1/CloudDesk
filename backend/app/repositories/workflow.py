from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import (
    ApprovalRequest,
    CustomerMemory,
    Escalation,
    ResolutionAction,
    WorkflowEvent,
    WorkflowRun,
)
from backend.app.repositories.base import BaseRepository


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkflowRun)

    async def get_by_thread_id(self, thread_id: str) -> WorkflowRun | None:
        statement = select(WorkflowRun).where(WorkflowRun.thread_id == thread_id)
        return await self.session.scalar(statement)

    async def list_for_ticket(self, ticket_id: str) -> list[WorkflowRun]:
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.ticket_id == ticket_id)
            .order_by(WorkflowRun.created_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get_latest_for_ticket(self, ticket_id: str) -> WorkflowRun | None:
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.ticket_id == ticket_id)
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
            .limit(1)
        )
        return await self.session.scalar(statement)


class WorkflowEventRepository(BaseRepository[WorkflowEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkflowEvent)

    async def list_for_run(self, workflow_run_id: str) -> list[WorkflowEvent]:
        statement = (
            select(WorkflowEvent)
            .where(WorkflowEvent.workflow_run_id == workflow_run_id)
            .order_by(WorkflowEvent.created_at, WorkflowEvent.id)
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class ResolutionActionRepository(BaseRepository[ResolutionAction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ResolutionAction)

    async def list_for_run(self, workflow_run_id: str) -> list[ResolutionAction]:
        statement = (
            select(ResolutionAction)
            .where(ResolutionAction.workflow_run_id == workflow_run_id)
            .order_by(ResolutionAction.created_at, ResolutionAction.id)
        )
        result = await self.session.scalars(statement)
        return list(result.all())


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ApprovalRequest)

    async def list_for_ticket(self, ticket_id: str) -> list[ApprovalRequest]:
        statement = (
            select(ApprovalRequest)
            .where(ApprovalRequest.ticket_id == ticket_id)
            .order_by(ApprovalRequest.requested_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[ApprovalRequest]:
        self._validate_pagination(limit, offset)
        statement = (
            select(ApprovalRequest)
            .order_by(ApprovalRequest.requested_at.desc(), ApprovalRequest.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def get_latest_for_ticket(self, ticket_id: str) -> ApprovalRequest | None:
        statement = (
            select(ApprovalRequest)
            .where(ApprovalRequest.ticket_id == ticket_id)
            .order_by(ApprovalRequest.requested_at.desc(), ApprovalRequest.id)
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def list_pending_for_ticket(self, ticket_id: str) -> list[ApprovalRequest]:
        statement = (
            select(ApprovalRequest)
            .where(
                ApprovalRequest.ticket_id == ticket_id,
                ApprovalRequest.status == "pending",
            )
            .order_by(ApprovalRequest.requested_at)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def decide_if_pending(
        self,
        approval_id: str,
        *,
        status: str,
        decided_at: datetime,
        decided_by_id: str,
        reason: str | None,
    ) -> bool:
        statement = (
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.status == "pending",
            )
            .values(
                status=status,
                decided_at=decided_at,
                decided_by_id=decided_by_id,
                reason=reason,
            )
        )
        result = await self.session.execute(statement)
        return result.rowcount == 1


class EscalationRepository(BaseRepository[Escalation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Escalation)

    async def list_for_ticket(self, ticket_id: str) -> list[Escalation]:
        statement = (
            select(Escalation)
            .where(Escalation.ticket_id == ticket_id)
            .order_by(Escalation.created_at.desc())
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_open(self) -> list[Escalation]:
        statement = (
            select(Escalation)
            .where(Escalation.status == "open")
            .order_by(Escalation.created_at)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def list_filtered(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        team: str | None = None,
        ticket_id: str | None = None,
    ) -> list[Escalation]:
        self._validate_pagination(limit, offset)
        statement = select(Escalation)
        if status is not None:
            statement = statement.where(Escalation.status == status)
        if team is not None:
            statement = statement.where(Escalation.team == team)
        if ticket_id is not None:
            statement = statement.where(Escalation.ticket_id == ticket_id)
        statement = (
            statement.order_by(Escalation.created_at.desc(), Escalation.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def count_filtered(
        self,
        *,
        status: str | None = None,
        team: str | None = None,
        ticket_id: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(Escalation)
        if status is not None:
            statement = statement.where(Escalation.status == status)
        if team is not None:
            statement = statement.where(Escalation.team == team)
        if ticket_id is not None:
            statement = statement.where(Escalation.ticket_id == ticket_id)
        return await self.session.scalar(statement) or 0


class CustomerMemoryRepository(BaseRepository[CustomerMemory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CustomerMemory)

    async def list_for_customer(self, customer_id: str, *, limit: int = 10) -> list[CustomerMemory]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        statement = (
            select(CustomerMemory)
            .where(CustomerMemory.customer_id == customer_id)
            .order_by(CustomerMemory.created_at.desc(), CustomerMemory.id)
            .limit(limit)
        )
        result = await self.session.scalars(statement)
        return list(result.all())

    async def find_exact(
        self,
        customer_id: str,
        kind: str,
        content: str,
    ) -> CustomerMemory | None:
        statement = select(CustomerMemory).where(
            CustomerMemory.customer_id == customer_id,
            CustomerMemory.kind == kind,
            CustomerMemory.content == content,
        )
        return await self.session.scalar(statement)
