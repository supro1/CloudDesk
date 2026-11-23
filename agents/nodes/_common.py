from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from agents.workflow_context import WorkflowTracerProtocol, current_workflow_tracer
from backend.app.core.observability import WorkflowNodeObservation


class _NullTracer:
    @asynccontextmanager
    async def node(self, name: str) -> AsyncGenerator[WorkflowNodeObservation, None]:
        async def discard_event(**_: object) -> None:
            return None

        yield WorkflowNodeObservation(node_name=name, write_event=discard_event)


_NULL_TRACER = _NullTracer()


def tracer_for() -> WorkflowTracerProtocol:
    return current_workflow_tracer() or _NULL_TRACER


__all__ = ["tracer_for"]
