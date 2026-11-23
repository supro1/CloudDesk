from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.observability import (
    WorkflowNodeObservation,
    bind_node_observation,
    reset_node_observation,
)
from backend.app.repositories.workflow import WorkflowEventRepository

logger = logging.getLogger(__name__)


class WorkflowTracer:
    """Persist sanitized workflow telemetry without interrupting agent execution."""

    def __init__(
        self,
        workflow_run_id: str,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.workflow_run_id = workflow_run_id
        self.session_factory = session_factory
        self.estimated_cost: float | None = 0.0

    @asynccontextmanager
    async def node(self, name: str) -> AsyncGenerator[WorkflowNodeObservation, None]:
        started_at = perf_counter()
        await self.record(
            event_type="node_started",
            node_name=name,
            payload={"status": "started"},
        )
        observation = WorkflowNodeObservation(node_name=name, write_event=self.record)
        token = bind_node_observation(observation)
        try:
            yield observation
        except Exception as error:
            await self.record(
                event_type="error",
                node_name=name,
                payload={"error_type": type(error).__name__},
            )
            await self.record(
                event_type="node_completed",
                node_name=name,
                payload={"status": "failed"},
                duration_ms=round((perf_counter() - started_at) * 1000),
            )
            raise
        else:
            await self.record(
                event_type="node_completed",
                node_name=name,
                payload={"status": "completed"},
                duration_ms=round((perf_counter() - started_at) * 1000),
                input_tokens=observation.token_usage.get("input_tokens"),
                output_tokens=observation.token_usage.get("output_tokens"),
            )
        finally:
            reset_node_observation(token)

    async def record(
        self,
        *,
        event_type: str,
        node_name: str | None = None,
        tool_name: str | None = None,
        payload: Mapping[str, Any] | None = None,
        duration_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        estimated_cost: float | None = None,
    ) -> None:
        event_payload = dict(payload or {})
        event_payload.setdefault("cost_available", estimated_cost is not None)
        if event_type == "llm_called":
            if estimated_cost is None:
                self.estimated_cost = None
            elif self.estimated_cost is not None:
                self.estimated_cost += estimated_cost
        try:
            async with self.session_factory() as session:
                await WorkflowEventRepository(session).create(
                    workflow_run_id=self.workflow_run_id,
                    event_type=event_type,
                    node_name=node_name,
                    tool_name=tool_name,
                    payload=event_payload,
                    duration_ms=duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=Decimal(str(estimated_cost or 0)),
                )
                await session.commit()
        except Exception:  # noqa: BLE001 - observability must never interrupt a workflow
            logger.warning(
                "Workflow telemetry write failed for workflow_id=%s event_type=%s",
                self.workflow_run_id,
                event_type,
            )


__all__ = ["WorkflowTracer"]
