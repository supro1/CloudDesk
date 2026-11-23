from __future__ import annotations

from agents.specialists import TroubleshootingAgent
from backend.app.core.llm import FakeLLM
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import DiagnosisDraft, Evidence
from tests.agents.conftest import SupportToolState


async def test_troubleshooting_uses_status_evidence_and_category_playbook(
    tool_registry,
    support_tool_state: SupportToolState,
) -> None:
    support_tool_state.statuses["authentication"] = "degraded"
    fake = FakeLLM(
        {
            DiagnosisDraft: {
                "probable_causes": ["The identity provider certificate may be expired."],
                "steps": ["Confirm the current certificate expiration date."],
            }
        }
    )
    evidence = [
        Evidence(
            id="sso:0:0",
            title="SSO troubleshooting",
            source="kb://sso#certificates",
            snippet="Verify that the identity-provider certificate is current.",
            score=0.9,
            url="/knowledge/sso",
            article_id="sso",
        )
    ]

    result = await TroubleshootingAgent(tool_registry, fake).run(
        "The whole team cannot sign in after a certificate rotation.",
        TicketCategory.LOGIN_ISSUE,
        evidence,
    )

    assert result.service_status == {
        "service": "authentication",
        "status": "degraded",
    }
    assert result.steps[0].number == 1
    assert any("identity-provider configuration" in step.instruction for step in result.steps)
    assert "Verify that the identity-provider certificate" in fake.calls[0][2]
