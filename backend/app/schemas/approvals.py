from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApprovalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApprovalDecisionRequest(ApprovalModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else None
        return normalized or None


class ApprovalResponse(ApprovalModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    ticket_id: str
    workflow_run_id: str
    action: str
    summary: str
    status: str
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None = Field(validation_alias="decided_by_id")
    reason: str | None


class ApprovalPageResponse(ApprovalModel):
    items: list[ApprovalResponse]
    total: int
    limit: int
    offset: int


class ApprovalDecisionResponse(ApprovalModel):
    approval: ApprovalResponse
    workflow_status: str


__all__ = [
    "ApprovalDecisionRequest",
    "ApprovalDecisionResponse",
    "ApprovalPageResponse",
    "ApprovalResponse",
]
