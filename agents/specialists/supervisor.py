from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from agents.prompts import (
    SECURITY_PREAMBLE,
    SEVERITY_ASSESSMENT_PROMPT,
    SUPERVISOR_CLASSIFICATION_PROMPT,
    wrap_untrusted,
)
from agents.rules import rule_category, rule_severity, scan_for_injection
from backend.app.core.llm import FakeLLM, call_structured
from backend.app.schemas.workflow import (
    Classification,
    SeverityAssessment,
    TicketSeverity,
    TicketSummary,
)

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class SupervisorAgent:
    """Classify a ticket and assess severity with deterministic rules on top."""

    def __init__(self, llm: FakeLLM | BaseChatModel | None = None) -> None:
        self.llm = llm

    async def understand(self, subject: str, body: str) -> Classification:
        text = f"{subject}\n{body}".strip()
        response = await call_structured(
            Classification,
            system_prompt=f"{SECURITY_PREAMBLE}\n{SUPERVISOR_CLASSIFICATION_PROMPT}",
            user_prompt=(
                f"Ticket subject:\n{wrap_untrusted(subject)}\n"
                f"Customer message:\n{wrap_untrusted(body)}"
            ),
            llm=self.llm,
        )
        category = rule_category(text) or response.output.category
        return Classification(
            category=category,
            summary=response.output.summary,
            confidence=response.output.confidence,
            injection_detected=scan_for_injection(text),
        )

    async def assess_severity(
        self,
        subject: str,
        body: str,
        *,
        proposed_severity: TicketSeverity = "medium",
        plan_name: str | None = None,
    ) -> SeverityAssessment:
        if proposed_severity not in _SEVERITY_RANK:
            raise ValueError(f"Unsupported proposed severity: {proposed_severity}")
        text = f"{subject}\n{body}".strip()
        response = await call_structured(
            SeverityAssessment,
            system_prompt=f"{SECURITY_PREAMBLE}\n{SEVERITY_ASSESSMENT_PROMPT}",
            user_prompt=(
                f"Proposed severity: {proposed_severity}\n"
                f"Subscription plan: {wrap_untrusted(plan_name or 'unknown')}\n"
                f"Ticket:\n{wrap_untrusted(text)}"
            ),
            llm=self.llm,
        )
        baseline_severity = max(
            (proposed_severity, response.output.severity),
            key=_SEVERITY_RANK.__getitem__,
        )
        severity, policy_reason = rule_severity(
            text,
            baseline_severity,
            plan_name,
        )
        reason = policy_reason or response.output.reason
        if (
            _SEVERITY_RANK[proposed_severity]
            > _SEVERITY_RANK[response.output.severity]
        ):
            reason = (
                f"Retained the higher proposed {proposed_severity} severity. "
                f"Model assessment: {response.output.reason}"
            )
        return SeverityAssessment(
            severity=severity,
            reason=policy_reason or reason,
        )

    @staticmethod
    def ticket_summary(
        classification: Classification,
        resolution_summary: str | None = None,
    ) -> TicketSummary:
        summary = resolution_summary or classification.summary
        return TicketSummary(summary=summary)


__all__ = ["SupervisorAgent"]
