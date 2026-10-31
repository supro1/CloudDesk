from __future__ import annotations

from sqlalchemy import select
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


class CustomerMemoryRepository(BaseRepository[CustomerMemory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CustomerMemory)

    async def list_for_customer(self, customer_id: str, *, limit: int = 10) -> list[CustomerMemory]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        statement = (
            select(CustomerMemory)
            .where(CustomerMemory.customer_id == customer_id)
            .order_by(CustomerMemory.created_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(statement)
        return list(result.all())
