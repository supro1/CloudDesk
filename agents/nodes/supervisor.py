from __future__ import annotations

from agents.nodes._common import tracer_for
from agents.specialists.supervisor import SupervisorAgent
from agents.state import SupportState

UNDERSTAND_TICKET = "understand_ticket"
CLASSIFY_SEVERITY = "classify_severity"


async def understand_ticket(state: SupportState) -> dict[str, object]:
    async with tracer_for().node(UNDERSTAND_TICKET) as observation:
        classification = await SupervisorAgent().understand(
            state["subject"],
            state["body"],
        )
    return {
        "classification": classification,
        "category": classification.category,
        "completed_nodes": [UNDERSTAND_TICKET],
        "current_node": UNDERSTAND_TICKET,
        "token_usage": observation.token_usage,
    }


async def classify_severity(state: SupportState) -> dict[str, object]:
    classification = state["classification"]
    async with tracer_for().node(CLASSIFY_SEVERITY) as observation:
        assessment = await SupervisorAgent().assess_severity(
            state["subject"],
            state["body"],
        )
    return {
        "severity_assessment": assessment,
        "severity": assessment.severity,
        "severity_reason": assessment.reason,
        "completed_nodes": [CLASSIFY_SEVERITY],
        "current_node": CLASSIFY_SEVERITY,
        "token_usage": observation.token_usage,
        "classification": classification,
    }


__all__ = [
    "CLASSIFY_SEVERITY",
    "UNDERSTAND_TICKET",
    "classify_severity",
    "understand_ticket",
]
