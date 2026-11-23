from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

from langgraph.types import interrupt

from agents.nodes._common import tracer_for
from agents.state import SupportState
from backend.app.schemas.workflow import EscalationDecision

_REJECTION_TEAMS = {
    "create_refund_request": "billing",
    "reset_demo_setting": "workspace_admin",
}


def create_human_approval_node() -> Callable[
    [SupportState], Awaitable[dict[str, object]]
]:
    async def human_approval(state: SupportState) -> dict[str, object]:
        approved_indices = list(state.get("approved_action_indices", []))
        plan = state["resolution_plan"]
        async with tracer_for().node("human_approval"):
            for index in state.get("approval_action_indices", []):
                if index in approved_indices:
                    continue
                action = plan.actions[index]
                response = interrupt(
                    {
                        "action_index": index,
                        "action": action.tool_name,
                        "summary": action.summary,
                    }
                )
                if not isinstance(response, Mapping):
                    raise TypeError("Approval resume data must be an object")

                decision = response.get("decision")
                reason_value = response.get("reason")
                reason = reason_value.strip() if isinstance(reason_value, str) else ""
                if decision == "approved":
                    approved_indices.append(index)
                    continue
                if decision != "rejected":
                    raise ValueError("Approval decision must be approved or rejected")

                team = _REJECTION_TEAMS.get(action.tool_name, "support_operations")
                escalation_reason = (
                    f"Human approval was rejected for {action.tool_name}."
                    + (f" Reviewer note: {reason}" if reason else "")
                )
                return {
                    "approval_decision": "rejected",
                    "approval_reason": reason or None,
                    "approved_action_indices": approved_indices,
                    "escalation_decision": EscalationDecision(
                        escalation_required=True,
                        team=team,
                        reason=escalation_reason,
                        confidence=1.0,
                        policy_rule="human_approval_rejected",
                    ),
                    "completed_nodes": ["human_approval"],
                    "current_node": "human_approval",
                }

        return {
            "approval_decision": "approved",
            "approved_action_indices": approved_indices,
            "completed_nodes": ["human_approval"],
            "current_node": "human_approval",
        }

    return human_approval


__all__ = ["create_human_approval_node"]
