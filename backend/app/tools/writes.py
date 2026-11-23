from __future__ import annotations

from decimal import Decimal, InvalidOperation

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.repositories import (
    EscalationRepository,
    TicketRepository,
    WorkflowRunRepository,
    WorkspaceRepository,
)
from integrations.protocols import BillingIntegration, WorkspaceIntegration

SessionFactory = async_sessionmaker[AsyncSession]
_TICKET_STATUSES = frozenset(
    {
        "new",
        "in_progress",
        "waiting_on_customer",
        "waiting_on_approval",
        "escalated",
        "resolved",
        "closed",
    }
)


def create_write_tools(
    session_factory: SessionFactory,
    billing: BillingIntegration,
    workspace: WorkspaceIntegration,
) -> list[BaseTool]:
    @tool
    async def update_ticket(
        ticket_id: str,
        status: str | None = None,
        summary: str | None = None,
    ) -> dict[str, object]:
        """Update an existing ticket's status or internal summary."""
        values: dict[str, str] = {}
        if status is not None:
            if status not in _TICKET_STATUSES:
                raise ValueError("status is not a supported ticket status")
            values["status"] = status
        if summary is not None:
            if not summary.strip():
                raise ValueError("summary must not be empty")
            values["summary"] = summary.strip()
        if not values:
            raise ValueError("At least one ticket field must be provided")

        async with session_factory() as session:
            ticket = await TicketRepository(session).update(ticket_id, values)
            if ticket is None:
                raise ValueError("Ticket not found")
            await session.commit()
            return {
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "status": ticket.status,
                "summary": ticket.summary,
            }

    @tool
    async def create_refund_request(
        ticket_id: str,
        customer_id: str,
        amount: str,
        reason: str,
    ) -> dict[str, object]:
        """Create a simulated refund request after human approval; no money is moved."""
        try:
            refund_amount = Decimal(amount)
        except (InvalidOperation, ValueError) as error:
            raise ValueError("amount must be a valid positive decimal") from error
        if not refund_amount.is_finite() or refund_amount <= 0:
            raise ValueError("amount must be a valid positive decimal")
        if not reason.strip():
            raise ValueError("reason must not be empty")

        async with session_factory() as session:
            ticket = await TicketRepository(session).get(ticket_id)
            if ticket is None:
                raise ValueError("Ticket not found")
            if ticket.customer_id != customer_id:
                raise ValueError("Ticket does not belong to the supplied customer")
        return dict(
            await billing.create_refund_request(
                ticket_id=ticket_id,
                customer_id=customer_id,
                amount=refund_amount,
                reason=reason.strip(),
            )
        )

    @tool
    async def reset_demo_setting(
        workspace_id: str,
        setting_name: str,
    ) -> dict[str, object]:
        """Reset a supported demo workspace setting after human approval."""
        async with session_factory() as session:
            workspace_record = await WorkspaceRepository(session).get(workspace_id)
            if workspace_record is None:
                raise ValueError("Workspace not found")
        return dict(
            await workspace.reset_setting(
                workspace_id=workspace_id,
                setting_name=setting_name,
            )
        )

    @tool
    async def create_escalation(
        ticket_id: str,
        team: str,
        reason: str,
        workflow_run_id: str | None = None,
    ) -> dict[str, object]:
        """Record a ticket escalation for a named support team."""
        normalized_team = team.strip()
        normalized_reason = reason.strip()
        if not normalized_team or len(normalized_team) > 120:
            raise ValueError("team must contain 1 to 120 characters")
        if not normalized_reason:
            raise ValueError("reason must not be empty")

        async with session_factory() as session:
            ticket = await TicketRepository(session).get(ticket_id)
            if ticket is None:
                raise ValueError("Ticket not found")
            if workflow_run_id is not None:
                workflow = await WorkflowRunRepository(session).get(workflow_run_id)
                if workflow is None or workflow.ticket_id != ticket.id:
                    raise ValueError("Workflow run does not belong to the ticket")
            escalation = await EscalationRepository(session).create(
                ticket_id=ticket.id,
                workflow_run_id=workflow_run_id,
                team=normalized_team,
                reason=normalized_reason,
                status="open",
            )
            await session.commit()
            return {
                "escalation_id": escalation.id,
                "ticket_id": ticket.id,
                "team": escalation.team,
                "reason": escalation.reason,
                "status": escalation.status,
            }

    return [
        update_ticket,
        create_refund_request,
        reset_demo_setting,
        create_escalation,
    ]
