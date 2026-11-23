from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    ticket_id: str
    workflow_run_id: str | None
    team: str
    reason: str
    status: str
    resolved_at: datetime | None
    created_at: datetime


class EscalationPageResponse(BaseModel):
    items: list[EscalationResponse]
    total: int
    limit: int
    offset: int


__all__ = ["EscalationPageResponse", "EscalationResponse"]
