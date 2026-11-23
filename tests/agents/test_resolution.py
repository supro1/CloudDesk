from __future__ import annotations

import pytest

from agents.specialists import ResolutionAgent
from backend.app.core.llm import FakeLLM
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import (
    Classification,
    Diagnosis,
    DiagnosisStep,
    Evidence,
    ResolutionDraft,
)


def _resolution_inputs() -> tuple[Classification, Diagnosis, list[Evidence]]:
    classification = Classification(
        category=TicketCategory.BILLING,
        summary="The customer asks for a review of a seat charge.",
        confidence=0.9,
    )
    diagnosis = Diagnosis(
        probable_causes=["The current seat count may differ from the billed count."],
        steps=[
            DiagnosisStep(
                number=1,
                instruction="Compare active seats with the invoice line items.",
            )
        ],
        service_status=None,
    )
    evidence = [
        Evidence(
            id="billing:0:0",
            title="Billing and refund review",
            source="kb://billing-refunds#review",
            snippet="A support agent can submit a refund request for human review.",
            score=0.9,
            url="/knowledge/billing-refunds",
            article_id="billing-refunds",
        )
    ]
    return classification, diagnosis, evidence


async def test_resolution_blocks_unsafe_reply_and_plans_approval_gated_actions() -> None:
    classification, diagnosis, evidence = _resolution_inputs()
    fake = FakeLLM(
        {
            ResolutionDraft: {
                "summary": "The invoice requires review.",
                "customer_reply": (
                    "Visit https://backend:8000/admin; your password=secret123."
                ),
                "internal_notes": "Refund needs a human decision.",
            }
        }
    )

    plan = await ResolutionAgent(fake).run(
        "Refund request",
        "Please review the seat charge.",
        classification,
        diagnosis,
        evidence,
        ticket_id="ticket-1",
        customer_id="customer-1",
        refund_amount="12.50",
        workspace_id="workspace-1",
        reset_setting="sso",
    )

    assert not plan.output_valid
    assert plan.customer_reply == ""
    assert set(plan.output_issues) == {"secret_detected", "internal_url_detected"}
    assert [action.tool_name for action in plan.actions] == [
        "update_ticket",
        "create_refund_request",
        "reset_demo_setting",
    ]
    assert plan.actions[0].approval_required is False
    assert all(action.approval_required for action in plan.actions[1:])
    assert "create_refund_request" not in repr(fake.calls[0][2])


async def test_resolution_reply_includes_numbered_steps_and_citations() -> None:
    classification, diagnosis, evidence = _resolution_inputs()
    fake = FakeLLM(
        {
            ResolutionDraft: {
                "summary": "The seat charge is being reviewed.",
                "customer_reply": "We will review the billing details.",
                "internal_notes": "No account change has been made.",
            }
        }
    )

    plan = await ResolutionAgent(fake).run(
        "Refund request",
        "Please review the seat charge.",
        classification,
        diagnosis,
        evidence,
    )

    assert plan.output_valid
    assert "1. Compare active seats with the invoice line items." in plan.customer_reply
    assert "[Billing and refund review](/knowledge/billing-refunds)" in plan.customer_reply


async def test_resolution_requires_customer_and_ticket_for_refund_planning() -> None:
    classification, diagnosis, evidence = _resolution_inputs()
    with pytest.raises(ValueError, match="ticket_id and customer_id"):
        await ResolutionAgent(FakeLLM()).run(
            "Refund request",
            "Please review this charge.",
            classification,
            diagnosis,
            evidence,
            refund_amount="10.00",
        )
