from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.schemas.common import TicketCategory

TicketSeverity = Literal["low", "medium", "high", "critical"]
MemoryKind = Literal["preference", "past_issue", "troubleshooting", "note"]
PlannedTool = Literal["update_ticket", "create_refund_request", "reset_demo_setting"]


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Classification(WorkflowModel):
    category: TicketCategory
    summary: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)
    injection_detected: bool = False

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary must not be blank")
        return normalized


class SeverityAssessment(WorkflowModel):
    severity: TicketSeverity
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized


class CustomerMemoryNote(WorkflowModel):
    kind: MemoryKind
    content: str = Field(min_length=1)
    source_ticket_id: str | None = None


class CustomerContext(WorkflowModel):
    customer: dict[str, Any] | None
    subscriptions: list[dict[str, Any]]
    previous_tickets: list[dict[str, Any]]
    memory_notes: list[CustomerMemoryNote]


class Evidence(WorkflowModel):
    id: str
    title: str
    source: str
    snippet: str
    score: float = Field(ge=0, le=1)
    url: str
    article_id: str


class PreviousCase(WorkflowModel):
    ticket_number: str
    resolution: str
    steps: list[str]
    similarity: float = Field(default=0, ge=0, le=1)


class KnowledgeResult(WorkflowModel):
    evidence: list[Evidence]
    similar_cases: list[PreviousCase]


class DiagnosisStep(WorkflowModel):
    number: int = Field(ge=1)
    instruction: str = Field(min_length=1, max_length=500)

    @field_validator("instruction")
    @classmethod
    def normalize_instruction(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("instruction must not be blank")
        return normalized


class DiagnosisDraft(WorkflowModel):
    probable_causes: list[str] = Field(min_length=1, max_length=5)
    steps: list[str] = Field(min_length=1, max_length=8)


class Diagnosis(WorkflowModel):
    probable_causes: list[str] = Field(min_length=1, max_length=5)
    steps: list[DiagnosisStep] = Field(min_length=1, max_length=8)
    service_status: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_ordered_step_numbers(self) -> Diagnosis:
        if [step.number for step in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("diagnosis step numbers must be contiguous and start at one")
        return self


class ResolutionDraft(WorkflowModel):
    summary: str = Field(min_length=1, max_length=500)
    customer_reply: str = Field(max_length=4000)
    internal_notes: str = Field(max_length=4000)


class PlannedAction(WorkflowModel):
    tool_name: PlannedTool
    arguments: dict[str, Any]
    approval_required: bool
    summary: str = Field(min_length=1, max_length=500)


class ResolutionPlan(WorkflowModel):
    summary: str = Field(min_length=1, max_length=500)
    customer_reply: str = Field(max_length=4000)
    internal_notes: str = Field(max_length=4000)
    actions: list[PlannedAction]
    output_valid: bool
    output_issues: list[str]


class EscalationDecision(WorkflowModel):
    escalation_required: bool
    team: str | None = Field(default=None, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    policy_rule: str | None = None

    @model_validator(mode="after")
    def require_team_for_escalation(self) -> EscalationDecision:
        if self.escalation_required and not (self.team and self.team.strip()):
            raise ValueError("an escalation decision must name a team")
        return self


class TicketSummary(WorkflowModel):
    summary: str = Field(min_length=1, max_length=500)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary must not be blank")
        return normalized


__all__ = [
    "Classification",
    "CustomerContext",
    "CustomerMemoryNote",
    "Diagnosis",
    "DiagnosisDraft",
    "DiagnosisStep",
    "EscalationDecision",
    "Evidence",
    "KnowledgeResult",
    "MemoryKind",
    "PlannedAction",
    "PreviousCase",
    "ResolutionDraft",
    "ResolutionPlan",
    "SeverityAssessment",
    "TicketSeverity",
    "TicketSummary",
    "WorkflowModel",
]
