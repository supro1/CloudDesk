from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.common import TicketCategory

TicketStatus = Literal[
    "new",
    "in_progress",
    "waiting_on_customer",
    "waiting_on_approval",
    "escalated",
    "resolved",
    "closed",
]
TicketSeverity = Literal["low", "medium", "high", "critical"]
TicketChannel = Literal["email", "chat", "web", "api"]


class TicketCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    customer_id: UUID
    channel: TicketChannel
    external_id: str | None = Field(default=None, max_length=200)

    @field_validator("subject", "body")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class TicketPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TicketStatus | None = None
    category: TicketCategory | None = None
    severity: TicketSeverity | None = None
    severity_reason: str | None = None
    summary: str | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> TicketPatchRequest:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status cannot be null")
        return self


class TicketReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def reject_blank_body(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("body must not be blank")
        return normalized


class TicketEscalateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("team", "reason")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_number: str
    customer_id: str
    subject: str
    channel: TicketChannel
    status: TicketStatus
    category: TicketCategory | None
    severity: TicketSeverity | None
    severity_reason: str | None
    summary: str | None
    external_id: str | None
    created_at: datetime
    updated_at: datetime


class TicketMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ticket_id: str
    sender_type: str
    sender_name: str | None
    body: str
    is_internal: bool
    created_at: datetime


class TicketCustomerSummary(BaseModel):
    id: str
    name: str
    email: str
    company_name: str | None


class TicketWorkflowSummary(BaseModel):
    id: str
    status: str


class TicketApprovalSummary(BaseModel):
    id: str
    ticket_id: str
    workflow_id: str
    action: str
    summary: str
    status: str
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None


class TicketDetailResponse(TicketResponse):
    messages: list[TicketMessageResponse]
    customer: TicketCustomerSummary
    workflow: TicketWorkflowSummary | None = None
    approval: TicketApprovalSummary | None = None


class TicketPageResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    limit: int
    offset: int


__all__ = [
    "TicketApprovalSummary",
    "TicketCategory",
    "TicketChannel",
    "TicketCreateRequest",
    "TicketCustomerSummary",
    "TicketDetailResponse",
    "TicketEscalateRequest",
    "TicketMessageResponse",
    "TicketPageResponse",
    "TicketPatchRequest",
    "TicketReplyRequest",
    "TicketResponse",
    "TicketSeverity",
    "TicketStatus",
    "TicketWorkflowSummary",
]
