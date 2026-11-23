from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import (
    Classification,
    CustomerContext,
    Diagnosis,
    EscalationDecision,
    KnowledgeResult,
    ResolutionPlan,
    SeverityAssessment,
    TicketSummary,
)


def append_values(left: list[str], right: list[str]) -> list[str]:
    return [*left, *right]


def merge_usage(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    merged = dict(left)
    for key, value in right.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Token usage for {key!r} must be an integer")
        merged[key] = merged.get(key, 0) + value
    return merged


class SupportState(TypedDict, total=False):
    workflow_id: str
    ticket_id: str
    ticket_number: str
    customer_id: str
    subject: str
    body: str
    current_node: str
    completed_nodes: Annotated[list[str], append_values]
    errors: Annotated[list[str], append_values]
    token_usage: Annotated[dict[str, int], merge_usage]
    classification: Classification
    severity_assessment: SeverityAssessment
    customer_context: CustomerContext
    knowledge: KnowledgeResult
    diagnosis: Diagnosis
    resolution_plan: ResolutionPlan
    ticket_summary: TicketSummary
    escalation_decision: EscalationDecision
    category: TicketCategory
    severity: Literal["low", "medium", "high", "critical"]
    severity_reason: str
    risk_level: Literal["low", "high"]
    memory_updated_count: int


__all__ = ["SupportState", "append_values", "merge_usage"]
