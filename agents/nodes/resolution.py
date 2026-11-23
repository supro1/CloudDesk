from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.nodes._common import tracer_for
from agents.specialists.escalation import EscalationAgent
from agents.specialists.resolution import ResolutionAgent, requested_refund_amount
from agents.specialists.supervisor import SupervisorAgent
from agents.state import SupportState
from backend.app.repositories import ResolutionActionRepository, TicketRepository
from backend.app.tools.registry import ToolRegistry

RESOLUTION_PLANNING = "resolution_planning"
RISK_CHECK = "risk_check"
TICKET_SUMMARY = "ticket_summary"


def create_resolution_planning_node() -> Callable[
    [SupportState], Awaitable[dict[str, object]]
]:
    async def resolution_planning(state: SupportState) -> dict[str, object]:
        classification = state["classification"]
        refund_amount = (
            requested_refund_amount(f"{state['subject']}\n{state['body']}")
            if classification.category.value == "billing"
            else None
        )
        async with tracer_for().node(RESOLUTION_PLANNING) as observation:
            plan = await ResolutionAgent().run(
                state["subject"],
                state["body"],
                classification,
                state["diagnosis"],
                state["knowledge"].evidence,
                ticket_id=state["ticket_id"],
                customer_id=state["customer_id"],
                refund_amount=refund_amount,
                refund_reason=(
                    "Customer-requested billing adjustment; verify invoice details."
                    if refund_amount is not None
                    else None
                ),
            )
        return {
            "resolution_plan": plan,
            "completed_nodes": [RESOLUTION_PLANNING],
            "current_node": RESOLUTION_PLANNING,
            "token_usage": observation.token_usage,
        }

    return resolution_planning


def _plan_name(state: SupportState) -> str | None:
    subscriptions = state.get("customer_context")
    if subscriptions is None:
        return None
    for subscription in subscriptions.subscriptions:
        plan_name = subscription.get("plan_name")
        if isinstance(plan_name, str) and plan_name.strip():
            return plan_name
    return None


def _risk_level(
    state: SupportState,
    escalation_required: bool,
    approval_required: bool,
) -> str:
    plan = state["resolution_plan"]
    high_risk = (
        approval_required
        or escalation_required
        or state["severity"] == "critical"
        or state["classification"].injection_detected
        or not plan.output_valid
    )
    return "high" if high_risk else "low"


def create_risk_check_node(
    tools: ToolRegistry,
) -> Callable[[SupportState], Awaitable[dict[str, object]]]:
    async def risk_check(state: SupportState) -> dict[str, object]:
        async with tracer_for().node(RISK_CHECK) as observation:
            decision = await EscalationAgent(tools).run(
                state["subject"],
                state["body"],
                state["severity"],
                plan_name=_plan_name(state),
            )
        approval_action_indices = [
            index
            for index, action in enumerate(state["resolution_plan"].actions)
            if action.approval_required
            or tools.requires_approval(action.tool_name, action.arguments)
        ]
        return {
            "escalation_decision": decision,
            "risk_level": _risk_level(
                state,
                decision.escalation_required,
                bool(approval_action_indices),
            ),
            "approval_action_indices": approval_action_indices,
            "completed_nodes": [RISK_CHECK],
            "current_node": RISK_CHECK,
            "token_usage": observation.token_usage,
        }

    return risk_check


def create_execute_resolution_node(
    tools: ToolRegistry,
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[SupportState], Awaitable[dict[str, object]]]:
    async def execute_resolution(state: SupportState) -> dict[str, object]:
        results: list[dict[str, object]] = []
        approved_indices = set(state.get("approved_action_indices", []))
        async with tracer_for().node("execute_resolution"):
            for index, action in enumerate(state["resolution_plan"].actions):
                result = await tools.execute(
                    action.tool_name,
                    action.arguments,
                    approved=index in approved_indices,
                )
                action_status = (
                    "completed"
                    if result.ok
                    else "blocked"
                    if result.requires_approval
                    else "failed"
                )
                result_value = jsonable_encoder(result.result) if result.ok else None
                async with session_factory() as session:
                    await ResolutionActionRepository(session).create(
                        workflow_run_id=state["workflow_id"],
                        action_type=action.tool_name,
                        arguments=action.arguments,
                        status=action_status,
                        approval_required=(
                            action.approval_required
                            or tools.requires_approval(action.tool_name, action.arguments)
                        ),
                        result=(
                            result_value
                            if result.ok
                            else {
                                "error": result.error or "Tool execution failed.",
                                "error_type": result.error_type,
                            }
                        ),
                        executed_at=datetime.now(UTC) if result.ok else None,
                    )
                    await session.commit()
                results.append(
                    {
                        "action_index": index,
                        "tool_name": action.tool_name,
                        "status": action_status,
                        "result": result_value,
                        "error": result.error,
                    }
                )
        failures = [
            f"{item['tool_name']} was {item['status']}."
            for item in results
            if item["status"] != "completed"
        ]
        return {
            "resolution_results": results,
            "errors": failures,
            "completed_nodes": ["execute_resolution"],
            "current_node": "execute_resolution",
        }

    return execute_resolution


def create_ticket_summary_node(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[SupportState], Awaitable[dict[str, object]]]:
    async def ticket_summary(state: SupportState) -> dict[str, object]:
        resolution = state.get("resolution_plan")
        summary = SupervisorAgent.ticket_summary(
            state["classification"],
            resolution.summary if resolution is not None else None,
        )
        async with (
            tracer_for().node(TICKET_SUMMARY),
            session_factory() as session,
        ):
            updated_ticket = await TicketRepository(session).update(
                state["ticket_id"],
                {
                    "summary": summary.summary,
                    "category": state["category"],
                    "severity": state["severity"],
                    "severity_reason": state["severity_reason"],
                },
            )
            if updated_ticket is None:
                raise LookupError("Ticket disappeared while workflow was running")
            await session.commit()
        return {
            "ticket_summary": summary,
            "completed_nodes": [TICKET_SUMMARY],
            "current_node": TICKET_SUMMARY,
        }

    return ticket_summary


__all__ = [
    "RESOLUTION_PLANNING",
    "RISK_CHECK",
    "TICKET_SUMMARY",
    "create_execute_resolution_node",
    "create_resolution_planning_node",
    "create_risk_check_node",
    "create_ticket_summary_node",
]
