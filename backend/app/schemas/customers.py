from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.app.schemas.tickets import TicketResponse


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    company_name: str | None
    created_at: datetime
    updated_at: datetime


class CustomerPageResponse(BaseModel):
    items: list[CustomerResponse]
    total: int
    limit: int
    offset: int


class CustomerSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_name: str
    status: str
    seat_count: int
    seats_used: int
    storage_limit_bytes: int
    storage_used_bytes: int
    current_period_start: datetime | None
    current_period_end: datetime | None


class CustomerWorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    settings: dict[str, object]
    is_active: bool


class CustomerDetailResponse(BaseModel):
    customer: CustomerResponse
    subscriptions: list[CustomerSubscriptionResponse]
    workspaces: list[CustomerWorkspaceResponse]
    recent_tickets: list[TicketResponse]
