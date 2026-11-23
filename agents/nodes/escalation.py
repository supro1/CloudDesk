from __future__ import annotations

from collections.abc import Awaitable, Callable

from agents.nodes._common import tracer_for
from agents.specialists._tools import execute_tool
from agents.specialists.escalation import EscalationAgent
from agents.state import SupportState
from backend.app.tools.registry import ToolRegistry


def create_escalation_node(
    tools: ToolRegistry,
) -> Callable[[SupportState], Awaitable[dict[str, object]]]:
    async def escalation(state: SupportState) -> dict[str, object]:
        decision = state["escalation_decision"]
        if not decision.escalation_required or decision.team is None:
            raise ValueError("Escalation node requires a named-team decision")

        async with tracer_for().node("escalation"):
            record = await EscalationAgent(tools).record_escalation(
                decision,
                ticket_id=state["ticket_id"],
                workflow_run_id=state["workflow_id"],
            )
            await execute_tool(
                tools,
                "update_ticket",
                {
                    "ticket_id": state["ticket_id"],
                    "status": "escalated",
                },
            )
        return {
            "escalation_result": dict(record),
            "completed_nodes": ["escalation"],
            "current_node": "escalation",
        }

    return escalation


__all__ = ["create_escalation_node"]
