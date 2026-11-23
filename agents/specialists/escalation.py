from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.language_models import BaseChatModel

from agents.prompts import ESCALATION_PROMPT, SECURITY_PREAMBLE, wrap_untrusted
from agents.rules import matching_escalation_rules
from agents.specialists._tools import execute_tool
from backend.app.core.llm import FakeLLM, call_structured
from backend.app.schemas.workflow import EscalationDecision, TicketSeverity
from backend.app.tools.registry import ToolRegistry

_LOW_CONFIDENCE = 0.5
_HIGH_SEVERITIES = frozenset({"high", "critical"})


class EscalationAgent:
    """Apply mandatory escalation rules before considering model judgment."""

    def __init__(
        self,
        tools: ToolRegistry | None = None,
        llm: FakeLLM | BaseChatModel | None = None,
    ) -> None:
        self.tools = tools
        self.llm = llm

    async def run(
        self,
        subject: str,
        body: str,
        severity: TicketSeverity,
        *,
        plan_name: str | None = None,
    ) -> EscalationDecision:
        if severity not in {"low", "medium", "high", "critical"}:
            raise ValueError(f"Unsupported severity: {severity}")
        text = f"{subject}\n{body}".strip()
        matched_rules = matching_escalation_rules(text, plan_name)
        if matched_rules:
            rule = matched_rules[0]
            return EscalationDecision(
                escalation_required=True,
                team=rule.team,
                reason=rule.reason,
                confidence=1.0,
                policy_rule=rule.name,
            )

        response = await call_structured(
            EscalationDecision,
            system_prompt=f"{SECURITY_PREAMBLE}\n{ESCALATION_PROMPT}",
            user_prompt=(
                f"Severity: {severity}\n"
                f"Plan: {wrap_untrusted(plan_name or 'unknown')}\n"
                f"Ticket:\n{wrap_untrusted(text)}"
            ),
            llm=self.llm,
        )
        decision = response.output
        if (
            decision.escalation_required
            and severity not in _HIGH_SEVERITIES
            and decision.confidence < _LOW_CONFIDENCE
        ):
            return decision.model_copy(
                update={
                    "escalation_required": False,
                    "team": None,
                    "reason": (
                        "A low-confidence model escalation was not retained: "
                        f"{decision.reason}"
                    ),
                }
            )
        return decision

    async def record_escalation(
        self,
        decision: EscalationDecision,
        *,
        ticket_id: str,
        workflow_run_id: str | None = None,
    ) -> Mapping[str, Any]:
        if not decision.escalation_required or decision.team is None:
            raise ValueError("Only a required escalation can be recorded")
        if self.tools is None:
            raise RuntimeError("ToolRegistry is required to record an escalation")
        result = await execute_tool(
            self.tools,
            "create_escalation",
            {
                "ticket_id": ticket_id,
                "team": decision.team,
                "reason": decision.reason,
                "workflow_run_id": workflow_run_id,
            },
        )
        if not isinstance(result, Mapping):
            raise TypeError("create_escalation must return an object")
        return result


__all__ = ["EscalationAgent"]
