from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.entities import Ticket
from backend.app.repositories import (
    ApprovalRequestRepository,
    CustomerRepository,
    TicketMessageRepository,
    TicketRepository,
    WorkflowRunRepository,
)
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.escalations import EscalationResponse
from backend.app.schemas.tickets import (
    TicketApprovalSummary,
    TicketChannel,
    TicketCreateRequest,
    TicketCustomerSummary,
    TicketDetailResponse,
    TicketEscalateRequest,
    TicketMessageResponse,
    TicketPageResponse,
    TicketPatchRequest,
    TicketReplyRequest,
    TicketResponse,
    TicketSeverity,
    TicketStatus,
    TicketWorkflowSummary,
)
from backend.app.services.ticket_actions import (
    CustomerReplyRejectedError,
    TicketActionNotFoundError,
    TicketActionService,
)

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


def _ticket_response(ticket: Ticket) -> TicketResponse:
    return TicketResponse.model_validate(ticket)


@router.post(
    "",
    response_model=TicketDetailResponse,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    body: TicketCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
) -> TicketDetailResponse:
    customer_id = str(body.customer_id)
    customers = CustomerRepository(session)
    customer = await customers.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    tickets = TicketRepository(session)
    if body.external_id is not None and await tickets.get_by_external_id(
        body.channel, body.external_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A ticket with this channel and external_id already exists",
        )

    try:
        ticket = await tickets.create(
            ticket_number=await tickets.next_ticket_number(),
            customer_id=customer_id,
            subject=body.subject,
            channel=body.channel,
            status="new",
            external_id=body.external_id,
        )
        message = await TicketMessageRepository(session).create(
            ticket_id=ticket.id,
            sender_type="customer",
            body=body.body,
            is_internal=False,
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        if body.external_id is not None and await tickets.get_by_external_id(
            body.channel, body.external_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A ticket with this channel and external_id already exists",
            ) from error
        if await customers.get(customer_id) is None:
            raise HTTPException(status_code=404, detail="Customer not found") from error
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ticket number conflict; please retry",
        ) from error

    return TicketDetailResponse(
        **_ticket_response(ticket).model_dump(),
        messages=[TicketMessageResponse.model_validate(message)],
        customer=TicketCustomerSummary(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            company_name=customer.company_name,
        ),
    )


@router.get("", response_model=TicketPageResponse)
async def list_tickets(
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    category: TicketCategory | None = None,
    severity: TicketSeverity | None = None,
    channel: TicketChannel | None = None,
    customer_id: UUID | None = None,
) -> TicketPageResponse:
    tickets = TicketRepository(session)
    filters = {
        "status": status_filter,
        "category": category,
        "severity": severity,
        "channel": channel,
        "customer_id": str(customer_id) if customer_id is not None else None,
    }
    items = await tickets.list_filtered(limit=limit, offset=offset, **filters)
    total = await tickets.count_filtered(**filters)
    return TicketPageResponse(
        items=[_ticket_response(ticket) for ticket in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketDetailResponse,
    response_model_exclude_unset=True,
)
async def get_ticket(
    ticket_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
) -> TicketDetailResponse:
    tickets = TicketRepository(session)
    ticket = await tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    customer = await CustomerRepository(session).get(ticket.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    result = TicketDetailResponse(
        **_ticket_response(ticket).model_dump(),
        messages=[
            TicketMessageResponse.model_validate(message)
            for message in await TicketMessageRepository(session).list_for_ticket(ticket.id)
        ],
        customer=TicketCustomerSummary(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            company_name=customer.company_name,
        ),
    )
    workflow = await WorkflowRunRepository(session).get_latest_for_ticket(ticket.id)
    if workflow is not None:
        result.workflow = TicketWorkflowSummary(id=workflow.id, status=workflow.status)
    approval = await ApprovalRequestRepository(session).get_latest_for_ticket(ticket.id)
    if approval is not None:
        result.approval = TicketApprovalSummary(
            id=approval.id,
            ticket_id=approval.ticket_id,
            workflow_id=approval.workflow_run_id,
            action=approval.action,
            summary=approval.summary,
            status=approval.status,
            requested_at=approval.requested_at,
            decided_at=approval.decided_at,
            decided_by=approval.decided_by_id,
        )
    return result


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: str,
    body: TicketPatchRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
) -> TicketResponse:
    values = body.model_dump(exclude_unset=True)
    ticket = await TicketRepository(session).update(ticket_id, values)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await session.commit()
    return _ticket_response(ticket)


@router.post("/{ticket_id}/reply", response_model=TicketMessageResponse)
async def reply_to_ticket(
    ticket_id: str,
    body: TicketReplyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
) -> TicketMessageResponse:
    try:
        message = await TicketActionService(session).record_reply(
            ticket_id,
            body.body,
            sender_name=current_user.email,
        )
    except TicketActionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CustomerReplyRejectedError as error:
        raise HTTPException(
            status_code=422,
            detail=f"{error} Issues: {', '.join(error.issues)}",
        ) from error
    return TicketMessageResponse.model_validate(message)


@router.post("/{ticket_id}/request-info", response_model=TicketMessageResponse)
async def request_ticket_information(
    ticket_id: str,
    body: TicketReplyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
) -> TicketMessageResponse:
    try:
        message = await TicketActionService(session).record_reply(
            ticket_id,
            body.body,
            sender_name=current_user.email,
            request_customer_information=True,
        )
    except TicketActionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CustomerReplyRejectedError as error:
        raise HTTPException(
            status_code=422,
            detail=f"{error} Issues: {', '.join(error.issues)}",
        ) from error
    return TicketMessageResponse.model_validate(message)


@router.post("/{ticket_id}/escalate", response_model=EscalationResponse)
async def escalate_ticket(
    ticket_id: str,
    body: TicketEscalateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
) -> EscalationResponse:
    try:
        escalation = await TicketActionService(session).escalate(
            ticket_id,
            team=body.team,
            reason=body.reason,
        )
    except TicketActionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return EscalationResponse.model_validate(escalation)
