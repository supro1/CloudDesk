from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.guardrails import validate_customer_output
from backend.app.models.entities import Escalation, TicketMessage
from backend.app.repositories import (
    CustomerRepository,
    EscalationRepository,
    TicketMessageRepository,
    TicketRepository,
    WorkflowRunRepository,
)


class TicketActionNotFoundError(LookupError):
    pass


class CustomerReplyRejectedError(ValueError):
    def __init__(self, issues: tuple[str, ...]) -> None:
        super().__init__("The customer reply did not pass output validation.")
        self.issues = issues


class TicketActionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_reply(
        self,
        ticket_id: str,
        body: str,
        *,
        sender_name: str | None,
        request_customer_information: bool = False,
    ) -> TicketMessage:
        tickets = TicketRepository(self.session)
        ticket = await tickets.get(ticket_id)
        if ticket is None:
            raise TicketActionNotFoundError("Ticket not found")

        normalized_body = body.strip()
        forbidden_values = await CustomerRepository(
            self.session
        ).list_contact_values_excluding(ticket.customer_id)
        validation = validate_customer_output(
            normalized_body,
            forbidden_values=forbidden_values,
        )
        if not validation.valid:
            raise CustomerReplyRejectedError(validation.issues)

        message = await TicketMessageRepository(self.session).create(
            ticket_id=ticket.id,
            sender_type="agent",
            sender_name=sender_name,
            body=normalized_body,
            is_internal=False,
        )
        if request_customer_information:
            ticket.status = "waiting_on_customer"
        await self.session.commit()
        return message

    async def escalate(
        self,
        ticket_id: str,
        *,
        team: str,
        reason: str,
    ) -> Escalation:
        tickets = TicketRepository(self.session)
        ticket = await tickets.get(ticket_id)
        if ticket is None:
            raise TicketActionNotFoundError("Ticket not found")

        workflow = await WorkflowRunRepository(self.session).get_latest_for_ticket(ticket_id)
        escalation = await EscalationRepository(self.session).create(
            ticket_id=ticket.id,
            workflow_run_id=workflow.id if workflow is not None else None,
            team=team.strip(),
            reason=reason.strip(),
            status="open",
        )
        ticket.status = "escalated"
        await self.session.commit()
        return escalation


__all__ = [
    "CustomerReplyRejectedError",
    "TicketActionNotFoundError",
    "TicketActionService",
]
