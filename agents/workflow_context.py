from __future__ import annotations

from contextlib import AbstractAsyncContextManager, contextmanager
from contextvars import ContextVar, Token
from typing import Protocol

from backend.app.core.observability import WorkflowNodeObservation


class WorkflowTracerProtocol(Protocol):
    def node(
        self,
        name: str,
    ) -> AbstractAsyncContextManager[WorkflowNodeObservation]: ...


_current_tracer: ContextVar[WorkflowTracerProtocol | None] = ContextVar(
    "clouddesk_workflow_tracer",
    default=None,
)


@contextmanager
def bind_workflow_tracer(tracer: WorkflowTracerProtocol):
    token: Token[WorkflowTracerProtocol | None] = _current_tracer.set(tracer)
    try:
        yield
    finally:
        _current_tracer.reset(token)


def current_workflow_tracer() -> WorkflowTracerProtocol | None:
    return _current_tracer.get()


__all__ = [
    "WorkflowTracerProtocol",
    "bind_workflow_tracer",
    "current_workflow_tracer",
]
