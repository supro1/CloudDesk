from __future__ import annotations

from agents.specialists import EscalationAgent
from backend.app.core.llm import FakeLLM
from backend.app.schemas.workflow import EscalationDecision
from tests.agents.conftest import SupportToolState


async def test_escalation_policy_overrides_model_and_records_through_registry(
    tool_registry,
    support_tool_state: SupportToolState,
) -> None:
    fake = FakeLLM()
    agent = EscalationAgent(tool_registry, fake)

    decision = await agent.run(
        "Possible account breach",
        "We found suspicious logins from unknown locations.",
        "medium",
    )
    record = await agent.record_escalation(decision, ticket_id="ticket-1")

    assert decision.escalation_required
    assert decision.team == "security"
    assert decision.policy_rule == "security_incident"
    assert fake.calls == []
    assert record["team"] == "security"
    assert len(support_tool_state.escalations) == 1


async def test_escalation_suppresses_vague_low_confidence_model_decisions() -> None:
    fake = FakeLLM(
        {
            EscalationDecision: {
                "escalation_required": True,
                "team": "general",
                "reason": "The request may need more attention.",
                "confidence": 0.3,
            }
        }
    )

    decision = await EscalationAgent(llm=fake).run(
        "General product question",
        "Can you explain how this setting works?",
        "medium",
    )

    assert not decision.escalation_required
    assert decision.team is None
    assert "low-confidence" in decision.reason


async def test_escalation_keeps_low_confidence_decision_for_high_severity() -> None:
    fake = FakeLLM(
        {
            EscalationDecision: {
                "escalation_required": True,
                "team": "security",
                "reason": "Potential severe impact needs review.",
                "confidence": 0.3,
            }
        }
    )

    decision = await EscalationAgent(llm=fake).run(
        "Unusual account behavior",
        "The impact is not yet confirmed.",
        "critical",
    )

    assert decision.escalation_required
    assert decision.team == "security"
