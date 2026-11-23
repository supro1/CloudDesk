from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from langchain_core.language_models import BaseChatModel

from agents.prompts import RESOLUTION_PROMPT, SECURITY_PREAMBLE, wrap_untrusted
from backend.app.core.guardrails import validate_customer_output
from backend.app.core.llm import FakeLLM, call_structured
from backend.app.schemas.workflow import (
    Classification,
    Diagnosis,
    Evidence,
    PlannedAction,
    ResolutionDraft,
    ResolutionPlan,
)


class ResolutionAgent:
    """Draft grounded customer content and derive tool actions from trusted inputs."""

    def __init__(self, llm: FakeLLM | BaseChatModel | None = None) -> None:
        self.llm = llm

    async def run(
        self,
        subject: str,
        body: str,
        classification: Classification,
        diagnosis: Diagnosis,
        evidence: Sequence[Evidence],
        *,
        ticket_id: str | None = None,
        customer_id: str | None = None,
        refund_amount: str | Decimal | None = None,
        refund_reason: str | None = None,
        workspace_id: str | None = None,
        reset_setting: str | None = None,
        forbidden_values: Sequence[str] = (),
    ) -> ResolutionPlan:
        response = await call_structured(
            ResolutionDraft,
            system_prompt=f"{SECURITY_PREAMBLE}\n{RESOLUTION_PROMPT}",
            user_prompt=self._prompt(subject, body, classification, diagnosis, evidence),
            llm=self.llm,
        )
        draft = response.output
        reply = _ground_response(draft.customer_reply, diagnosis, evidence)
        validation = validate_customer_output(
            reply,
            forbidden_values=forbidden_values,
        )
        actions = plan_actions(
            draft.summary,
            classification.category.value,
            ticket_id=ticket_id,
            customer_id=customer_id,
            refund_amount=refund_amount,
            refund_reason=refund_reason,
            workspace_id=workspace_id,
            reset_setting=reset_setting,
        )
        return ResolutionPlan(
            summary=draft.summary,
            customer_reply=reply if validation.valid else "",
            internal_notes=draft.internal_notes,
            actions=actions,
            output_valid=validation.valid,
            output_issues=list(validation.issues),
        )

    @staticmethod
    def _prompt(
        subject: str,
        body: str,
        classification: Classification,
        diagnosis: Diagnosis,
        evidence: Sequence[Evidence],
    ) -> str:
        evidence_text = "\n".join(
            f"- {item.title}: {wrap_untrusted(item.snippet)}" for item in evidence
        )
        diagnosis_text = "\n".join(
            f"{step.number}. {wrap_untrusted(step.instruction)}"
            for step in diagnosis.steps
        )
        return (
            f"Ticket subject:\n{wrap_untrusted(subject)}\n"
            f"Ticket message:\n{wrap_untrusted(body)}\n"
            f"Category: {classification.category.value}\n"
            f"Ticket summary:\n{wrap_untrusted(classification.summary)}\n"
            f"Diagnosis:\n{diagnosis_text}\n"
            f"Knowledge evidence:\n{evidence_text or 'No cited evidence was found.'}"
        )


def plan_actions(
    summary: str,
    category: str,
    *,
    ticket_id: str | None = None,
    customer_id: str | None = None,
    refund_amount: str | Decimal | None = None,
    refund_reason: str | None = None,
    workspace_id: str | None = None,
    reset_setting: str | None = None,
) -> list[PlannedAction]:
    """Create allow-listed actions from explicit arguments, never model output."""
    if ticket_id is not None and not ticket_id.strip():
        raise ValueError("ticket_id must not be blank")
    if customer_id is not None and not customer_id.strip():
        raise ValueError("customer_id must not be blank")
    actions: list[PlannedAction] = []
    if ticket_id is not None:
        actions.append(
            PlannedAction(
                tool_name="update_ticket",
                arguments={"ticket_id": ticket_id, "summary": summary},
                approval_required=False,
                summary="Save the internal summary to the ticket.",
            )
        )

    if refund_amount is not None:
        if ticket_id is None or customer_id is None:
            raise ValueError("Refund planning requires both ticket_id and customer_id")
        try:
            amount = Decimal(str(refund_amount))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("refund_amount must be a positive decimal") from error
        if not amount.is_finite() or amount <= 0:
            raise ValueError("refund_amount must be a positive decimal")
        reason = (refund_reason or "").strip() or (
            f"Refund review requested for {category} support request."
        )
        actions.append(
            PlannedAction(
                tool_name="create_refund_request",
                arguments={
                    "ticket_id": ticket_id,
                    "customer_id": customer_id,
                    "amount": str(amount),
                    "reason": reason,
                },
                approval_required=True,
                summary="Request a human-reviewed refund; no money is moved automatically.",
            )
        )

    if workspace_id is not None or reset_setting is not None:
        if not workspace_id or not reset_setting:
            raise ValueError("Setting-reset planning requires workspace_id and reset_setting")
        if not workspace_id.strip() or not reset_setting.strip():
            raise ValueError("workspace_id and reset_setting must not be blank")
        actions.append(
            PlannedAction(
                tool_name="reset_demo_setting",
                arguments={
                    "workspace_id": workspace_id,
                    "setting_name": reset_setting,
                },
                approval_required=True,
                summary="Request human approval before changing a workspace setting.",
            )
        )
    return actions


def requested_refund_amount(text: str) -> str | None:
    """Return one explicitly stated currency amount for a customer-requested refund."""
    if not re.search(r"\b(?:refund|credit)\b", text, re.IGNORECASE):
        return None
    amounts = re.findall(
        r"(?<![\w.])\$\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)",
        text,
    )
    if len(amounts) != 1:
        return None
    try:
        amount = Decimal(amounts[0].replace(",", ""))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return str(amount)


def _ground_response(
    reply: str,
    diagnosis: Diagnosis,
    evidence: Sequence[Evidence],
) -> str:
    sections = [reply.strip()] if reply.strip() else []
    if diagnosis.steps:
        steps = "\n".join(
            f"{step.number}. {step.instruction}" for step in diagnosis.steps
        )
        sections.append(f"Recommended next steps:\n{steps}")
    if evidence:
        citations = "\n".join(
            f"- [{item.title}]({item.url}) ({item.source})" for item in evidence
        )
        sections.append(f"References:\n{citations}")
    return "\n\n".join(sections)


__all__ = ["ResolutionAgent", "plan_actions", "requested_refund_amount"]
