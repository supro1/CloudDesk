from __future__ import annotations

from agents.specialists import KnowledgeAgent
from backend.app.schemas.common import TicketCategory
from backend.app.schemas.workflow import PreviousCase
from tests.agents.conftest import SupportToolState


async def test_knowledge_agent_returns_cited_evidence_and_ranked_similar_cases(
    tool_registry,
    support_tool_state: SupportToolState,
) -> None:
    support_tool_state.evidence = [
        {
            "id": "mfa:0:0",
            "title": "MFA recovery",
            "source": "kb://mfa-recovery#reset",
            "snippet": "Use the documented MFA recovery procedure.",
            "score": 0.92,
            "url": "/knowledge/mfa-recovery",
            "article_id": "mfa-recovery",
        }
    ]
    previous_case = PreviousCase(
        ticket_number="CD-1012",
        resolution="Restored MFA access after identity verification.",
        steps=["Follow the approved MFA recovery procedure."],
    )
    agent = KnowledgeAgent(tool_registry, [previous_case])

    result = await agent.run(
        "MFA user locked out after failed sign-in attempts",
        category=TicketCategory.LOGIN_ISSUE,
        mode="hybrid",
        top_k=2,
    )

    assert result.evidence[0].source.startswith("kb://mfa-recovery")
    assert result.similar_cases[0].ticket_number == "CD-1012"
    assert result.similar_cases[0].similarity > 0


def test_knowledge_agent_loads_sample_resolutions_and_validates_query(
    tool_registry,
) -> None:
    agent = KnowledgeAgent(tool_registry)

    assert len(agent.previous_cases) == 3
    assert agent.similar_cases("unrelated words with no overlap") == []
