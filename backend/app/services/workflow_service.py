from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.state import SupportState
from agents.workflow_context import bind_workflow_tracer
from backend.app.models.entities import WorkflowEvent, WorkflowRun
from backend.app.repositories import (
    TicketMessageRepository,
    TicketRepository,
    WorkflowEventRepository,
    WorkflowRunRepository,
)
from backend.app.services.workflow_tracer import WorkflowTracer

logger = logging.getLogger(__name__)
_ACTIVE_STATUSES = frozenset({"queued", "running", "paused"})


class TicketNotFoundError(LookupError):
    pass


class WorkflowConflictError(RuntimeError):
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
        tracer = WorkflowTracer(workflow_id, self.session_factory)
        started_at = datetime.now(UTC)
        await self._update_run(
            workflow_id,
            status="running",
            started_at=started_at,
        )
        final_state: dict[str, Any] | None = None
        try:
            config = {"configurable": {"thread_id": run.thread_id or run.id}}
            with bind_workflow_tracer(tracer):
                async for state in self.graph.astream(
                    initial_state,
                    config=config,
                    stream_mode="values",
                ):
                    final_state = dict(state)
                    await self._save_progress(workflow_id, final_state)
            if final_state is None:
                raise RuntimeError("The workflow graph produced no state updates")
            finished_at = datetime.now(UTC)
            usage = final_state.get("token_usage", {})
            await self._update_run(
                workflow_id,
                status="completed",
                state=jsonable_encoder(final_state),
                token_usage=usage,
                estimated_cost=Decimal(str(tracer.estimated_cost or 0)),
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
                workflow_id,
                status="failed",
                state=jsonable_encoder(final_state or initial_state),
                error="Workflow execution failed; inspect server logs.",
                finished_at=datetime.now(UTC),
            )
            logger.error(
                "Workflow execution failed for workflow_id=%s error_type=%s",
                workflow_id,
                type(error).__name__,
            )
            raise

    async def get_latest_run(self, ticket_id: str) -> WorkflowRun | None:
        async with self.session_factory() as session:
            return await WorkflowRunRepository(session).get_latest_for_ticket(ticket_id)

    async def list_events(self, workflow_run_id: str) -> list[WorkflowEvent]:
        async with self.session_factory() as session:
            return await WorkflowEventRepository(session).list_for_run(workflow_run_id)

    async def _get_run(self, workflow_id: str) -> WorkflowRun | None:
        async with self.session_factory() as session:
            return await WorkflowRunRepository(session).get(workflow_id)

    async def _save_progress(self, workflow_id: str, state: dict[str, Any]) -> None:
        await self._update_run(
            workflow_id,
            status="running",
            state=jsonable_encoder(state),
            token_usage=state.get("token_usage", {}),
        )

    async def _update_run(self, workflow_id: str, **values: Any) -> None:
        async with self.session_factory() as session:
            updated = await WorkflowRunRepository(session).update(workflow_id, values)
            if updated is None:
                raise LookupError("Workflow run disappeared during execution")
            await session.commit()


__all__ = [
    "TicketNotFoundError",
    "WorkflowConflictError",
    "WorkflowService",
]
