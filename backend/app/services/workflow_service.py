from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.state import SupportState
from agents.workflow_context import bind_workflow_tracer
from backend.app.models.entities import ApprovalRequest, WorkflowEvent, WorkflowRun
from backend.app.repositories import (
    ApprovalRequestRepository,
    TicketMessageRepository,
    TicketRepository,
    WorkflowEventRepository,
    WorkflowRunRepository,
)
from backend.app.schemas.workflow import ResolutionPlan
from backend.app.services.workflow_tracer import WorkflowTracer

logger = logging.getLogger(__name__)
_ACTIVE_STATUSES = frozenset({"queued", "running", "paused"})


class TicketNotFoundError(LookupError):
    pass


class WorkflowConflictError(RuntimeError):
    pass


class ApprovalNotFoundError(LookupError):
    pass


class ApprovalConflictError(RuntimeError):
    pass


class WorkflowService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        graph: CompiledStateGraph,
    ) -> None:
        self.session_factory = session_factory
        self.graph = graph

    async def create_run(self, ticket_id: str) -> WorkflowRun:
        async with self.session_factory() as session:
            tickets = TicketRepository(session)
            ticket = await tickets.get(ticket_id)
            if ticket is None:
                raise TicketNotFoundError("Ticket not found")
            if ticket.status == "waiting_on_approval":
                raise WorkflowConflictError("Ticket is waiting on human approval")

            runs = WorkflowRunRepository(session)
            latest = await runs.get_latest_for_ticket(ticket_id)
            if latest is not None and latest.status in _ACTIVE_STATUSES:
                raise WorkflowConflictError("A workflow is already active for this ticket")

            messages = await TicketMessageRepository(session).list_for_ticket(ticket_id)
            body = "\n\n".join(
                message.body
                for message in messages
                if message.sender_type == "customer" and not message.is_internal
            )
            run = await runs.create(
                ticket_id=ticket_id,
                status="queued",
                state={},
            )
            initial_state: SupportState = {
                "workflow_id": run.id,
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "customer_id": ticket.customer_id,
                "subject": ticket.subject,
                "body": body,
                "completed_nodes": [],
                "errors": [],
                "token_usage": {"input_tokens": 0, "output_tokens": 0},
            }
            await runs.update(
                run.id,
                {"thread_id": run.id, "state": jsonable_encoder(initial_state)},
            )
            await tickets.update(ticket_id, {"status": "in_progress"})
            await session.commit()
            return run

    async def start_workflow(self, workflow_id: str) -> None:
        run = await self._get_run(workflow_id)
        if run is None:
            raise LookupError("Workflow run not found")
        initial_state = SupportState(**run.state)
        started_at = datetime.now(UTC)
        await self._update_run(
            workflow_id,
            status="running",
            started_at=started_at,
        )
        await self._run_graph(run, initial_state)

    async def decide_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        reason: str | None,
        decided_by_id: str,
    ) -> tuple[ApprovalRequest, WorkflowRun]:
        async with self.session_factory() as session:
            approvals = ApprovalRequestRepository(session)
            approval = await approvals.get(approval_id)
            if approval is None:
                raise ApprovalNotFoundError("Approval request not found")
            if approval.status != "pending":
                raise ApprovalConflictError("Approval request has already been decided")

            runs = WorkflowRunRepository(session)
            run = await runs.get(approval.workflow_run_id)
            if run is None or run.ticket_id != approval.ticket_id:
                raise ApprovalConflictError("Approval request has no matching workflow")
            if run.status != "paused":
                raise ApprovalConflictError("Workflow is not paused for approval")

            decided_at = datetime.now(UTC)
            decision_status = "approved" if approved else "rejected"
            updated = await approvals.decide_if_pending(
                approval_id,
                status=decision_status,
                decided_at=decided_at,
                decided_by_id=decided_by_id,
                reason=reason,
            )
            if not updated:
                raise ApprovalConflictError("Approval request has already been decided")
            approval.status = decision_status
            approval.decided_at = decided_at
            approval.decided_by_id = decided_by_id
            approval.reason = reason
            ticket = await TicketRepository(session).get(approval.ticket_id)
            if ticket is None:
                raise TicketNotFoundError("Ticket not found")
            ticket.status = "in_progress"
            await session.commit()
            thread_id = run.thread_id or run.id

        tracer = WorkflowTracer(run.id, self.session_factory)
        decision = "approved" if approved else "rejected"
        await tracer.record(
            event_type="approval_resolved",
            payload={"action": approval.action, "decision": decision},
        )
        await self._update_run(run.id, status="running")
        await self._run_graph(
            run,
            Command(resume={"decision": decision, "reason": reason}),
            thread_id=thread_id,
        )

        async with self.session_factory() as session:
            decided_approval = await ApprovalRequestRepository(session).get(approval_id)
            updated_run = await WorkflowRunRepository(session).get(run.id)
            if decided_approval is None or updated_run is None:
                raise LookupError("Approval or workflow disappeared after resuming")
            return decided_approval, updated_run

    async def get_latest_run(self, ticket_id: str) -> WorkflowRun | None:
        async with self.session_factory() as session:
            return await WorkflowRunRepository(session).get_latest_for_ticket(ticket_id)

    async def list_events(self, workflow_run_id: str) -> list[WorkflowEvent]:
        async with self.session_factory() as session:
            return await WorkflowEventRepository(session).list_for_run(workflow_run_id)

    async def _get_run(self, workflow_id: str) -> WorkflowRun | None:
        async with self.session_factory() as session:
            return await WorkflowRunRepository(session).get(workflow_id)

    async def _run_graph(
        self,
        run: WorkflowRun,
        graph_input: SupportState | Command,
        *,
        thread_id: str | None = None,
    ) -> None:
        tracer = WorkflowTracer(run.id, self.session_factory)
        started_at = datetime.now(UTC)
        final_state: dict[str, Any] | None = (
            dict(run.state) if isinstance(run.state, dict) else None
        )
        config = {"configurable": {"thread_id": thread_id or run.thread_id or run.id}}
        try:
            with bind_workflow_tracer(tracer):
                async for state in self.graph.astream(
                    graph_input,
                    config=config,
                    stream_mode="values",
                ):
                    final_state = dict(state)
                    await self._save_progress(run.id, final_state)
            if final_state is None:
                raise RuntimeError("The workflow graph produced no state updates")

            interrupt_payload = _approval_interrupt(final_state)
            if interrupt_payload is not None:
                await self._pause_for_approval(run.id, final_state, interrupt_payload, tracer)
                return

            finished_at = datetime.now(UTC)
            usage = final_state.get("token_usage", {})
            action_errors = final_state.get("errors", [])
            completion_error = (
                "One or more planned actions did not complete; inspect workflow events."
                if action_errors
                else None
            )
            await self._update_run(
                run.id,
                status="completed",
                state=jsonable_encoder(_persisted_state(final_state)),
                token_usage=usage,
                estimated_cost=Decimal(str(tracer.estimated_cost or 0)),
                error=completion_error,
                finished_at=finished_at,
            )
            await tracer.record(
                event_type="workflow_completed",
                payload={
                    "status": "completed",
                    "duration_ms": round((finished_at - started_at).total_seconds() * 1000),
                },
                duration_ms=round((finished_at - started_at).total_seconds() * 1000),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                estimated_cost=tracer.estimated_cost,
            )
        except Exception as error:
            await tracer.record(
                event_type="error",
                payload={"error_type": type(error).__name__},
            )
            await self._update_run(
                run.id,
                status="failed",
                state=jsonable_encoder(_persisted_state(final_state or {})),
                error="Workflow execution failed; inspect server logs.",
                finished_at=datetime.now(UTC),
            )
            logger.error(
                "Workflow execution failed for workflow_id=%s error_type=%s",
                run.id,
                type(error).__name__,
            )
            raise

    async def _pause_for_approval(
        self,
        workflow_id: str,
        state: dict[str, Any],
        interrupt_payload: Mapping[str, Any],
        tracer: WorkflowTracer,
    ) -> None:
        action_index = interrupt_payload.get("action_index")
        if not isinstance(action_index, int) or isinstance(action_index, bool):
            raise TypeError("Approval interrupt did not identify a planned action")
        plan = ResolutionPlan.model_validate(state.get("resolution_plan"))
        if action_index < 0 or action_index >= len(plan.actions):
            raise RuntimeError("Approval interrupt references an unknown planned action")
        action = plan.actions[action_index]
        payload_action = interrupt_payload.get("action")
        if payload_action != action.tool_name:
            raise RuntimeError("Approval interrupt action does not match the resolution plan")
        paused_state = _persisted_state(state)
        paused_state["current_node"] = "human_approval"

        async with self.session_factory() as session:
            run = await WorkflowRunRepository(session).get(workflow_id)
            if run is None:
                raise LookupError("Workflow run disappeared while requesting approval")
            tickets = TicketRepository(session)
            ticket = await tickets.get(run.ticket_id)
            if ticket is None:
                raise LookupError("Ticket disappeared while requesting approval")
            approvals = ApprovalRequestRepository(session)
            pending = await approvals.list_pending_for_ticket(ticket.id)
            approval = next(
                (
                    request
                    for request in pending
                    if request.workflow_run_id == workflow_id
                    and request.action == action.tool_name
                ),
                None,
            )
            if approval is None:
                approval = await approvals.create(
                    ticket_id=ticket.id,
                    workflow_run_id=workflow_id,
                    action=action.tool_name,
                    summary=action.summary,
                    status="pending",
                )
            ticket.status = "waiting_on_approval"
            run.status = "paused"
            run.state = jsonable_encoder(paused_state)
            await session.commit()

        await tracer.record(
            event_type="approval_requested",
            payload={
                "approval_id": approval.id,
                "action": approval.action,
                "summary": approval.summary,
            },
        )

    async def _save_progress(self, workflow_id: str, state: dict[str, Any]) -> None:
        await self._update_run(
            workflow_id,
            status="running",
            state=jsonable_encoder(_persisted_state(state)),
            token_usage=state.get("token_usage", {}),
        )

    async def _update_run(self, workflow_id: str, **values: Any) -> None:
        async with self.session_factory() as session:
            updated = await WorkflowRunRepository(session).update(workflow_id, values)
            if updated is None:
                raise LookupError("Workflow run disappeared during execution")
            await session.commit()


def _persisted_state(state: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "__interrupt__"}


def _approval_interrupt(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    interrupts = state.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0] if isinstance(interrupts, (tuple, list)) else None
    payload = getattr(first, "value", None)
    if not isinstance(payload, Mapping):
        raise TypeError("Workflow yielded an invalid approval interrupt")
    return payload


__all__ = [
    "ApprovalConflictError",
    "ApprovalNotFoundError",
    "TicketNotFoundError",
    "WorkflowConflictError",
    "WorkflowService",
]
