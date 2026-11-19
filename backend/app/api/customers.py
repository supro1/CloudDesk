from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories import (
    CustomerRepository,
    SubscriptionRepository,
    TicketRepository,
    WorkspaceRepository,
)
from backend.app.schemas.customers import (
    CustomerDetailResponse,
    CustomerPageResponse,
    CustomerResponse,
    CustomerSubscriptionResponse,
    CustomerWorkspaceResponse,
)
from backend.app.schemas.tickets import TicketResponse

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=CustomerPageResponse)
async def list_customers(
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    email: str | None = None,
    company_name: str | None = None,
) -> CustomerPageResponse:
    customers = CustomerRepository(session)
    filters = {"email": email, "company_name": company_name}
    items = await customers.list_filtered(limit=limit, offset=offset, **filters)
    total = await customers.count_filtered(**filters)
    return CustomerPageResponse(
        items=[CustomerResponse.model_validate(customer) for customer in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{customer_id}", response_model=CustomerDetailResponse)
async def get_customer(
    customer_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
) -> CustomerDetailResponse:
    customer_id_str = str(customer_id)
    customer = await CustomerRepository(session).get(customer_id_str)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    return CustomerDetailResponse(
        customer=CustomerResponse.model_validate(customer),
        subscriptions=[
            CustomerSubscriptionResponse.model_validate(subscription)
            for subscription in await SubscriptionRepository(session).list_for_customer(
                customer_id_str
            )
        ],
        workspaces=[
            CustomerWorkspaceResponse.model_validate(workspace)
            for workspace in await WorkspaceRepository(session).list_for_customer(
                customer_id_str
            )
        ],
        recent_tickets=[
            TicketResponse.model_validate(ticket)
            for ticket in await TicketRepository(session).list_for_customer(
                customer_id_str, limit=20
            )
        ],
    )
