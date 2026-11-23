from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

EventWriter = Callable[..., Awaitable[None]]


def summarize_tool_result(tool_name: str, result: Any) -> dict[str, Any]:
    if result is None:
        return {"found": False}
    if isinstance(result, list):
        summary: dict[str, Any] = {"count": len(result)}
        if tool_name == "search_docs":
            summary["articles"] = [
                {
                    key: item[key]
                    for key in ("article_id", "title", "source", "score")
                    if key in item
                }
                for item in result
                if isinstance(item, Mapping)
            ]
        elif tool_name == "get_subscription":
            summary["subscriptions"] = [
                {
                    key: item[key]
                    for key in ("plan_name", "status")
                    if key in item
                }
                for item in result
                if isinstance(item, Mapping)
            ]
        elif tool_name == "get_ticket_history":
            summary["statuses"] = sorted(
                {
                    item["status"]
                    for item in result
                    if isinstance(item, Mapping)
                    and isinstance(item.get("status"), str)
                }
            )
            summary["categories"] = sorted(
                {
                    item["category"]
                    for item in result
                    if isinstance(item, Mapping)
                    and isinstance(item.get("category"), str)
                }
            )
        return summary
    if isinstance(result, Mapping):
        if tool_name == "get_customer":
            workspaces = result.get("workspaces")
            return {
                "found": True,
                "workspace_count": len(workspaces) if isinstance(workspaces, list) else 0,
            }
        if tool_name == "check_service_status":
            summary = {
                key: result[key]
                for key in ("service_name", "status")
                if isinstance(result.get(key), (str, bool))
            }
            incidents = result.get("active_incidents")
            if isinstance(incidents, list):
                summary["active_incident_count"] = len(incidents)
            return summary
        if tool_name == "update_ticket":
            return {
                key: result[key]
                for key in ("ticket_number", "status")
                if isinstance(result.get(key), str)
            } | {"updated": True}
        if tool_name == "create_escalation":
            return {
                key: result[key]
                for key in ("team", "status")
                if isinstance(result.get(key), str)
            } | {"recorded": True}
        if tool_name in {"create_refund_request", "reset_demo_setting"}:
            return {
                key: result[key]
                for key in ("status",)
                if isinstance(result.get(key), str)
            }
        return {"field_count": len(result)}
    return {"result_type": type(result).__name__}


@dataclass(slots=True)
class WorkflowNodeObservation:
    node_name: str
    write_event: EventWriter
    token_usage: dict[str, int] = field(
        default_factory=lambda: {"input_tokens": 0, "output_tokens": 0}
    )

    async def record_llm_call(
        self,
        *,
        schema_name: str,
        usage: Mapping[str, int],
        duration_ms: float,
        estimated_cost: float | None,
    ) -> None:
        for key in ("input_tokens", "output_tokens"):
            self.token_usage[key] = self.token_usage.get(key, 0) + usage.get(key, 0)
        await self.write_event(
            event_type="llm_called",
            node_name=self.node_name,
            payload={
                "schema": schema_name,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "estimated_cost": estimated_cost,
                "cost_available": estimated_cost is not None,
            },
            duration_ms=round(duration_ms),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            estimated_cost=estimated_cost,
        )

    async def record_tool_call(
        self,
        *,
        tool_name: str,
        ok: bool,
        error_type: str | None,
        requires_approval: bool,
        result_summary: Mapping[str, Any] | None,
        duration_ms: float,
    ) -> None:
        await self.write_event(
            event_type="tool_called",
            node_name=self.node_name,
            tool_name=tool_name,
            payload={
                "ok": ok,
                "error_type": error_type,
                "requires_approval": requires_approval,
                "result_summary": dict(result_summary) if result_summary is not None else None,
            },
            duration_ms=round(duration_ms),
        )


_current_observation: ContextVar[WorkflowNodeObservation | None] = ContextVar(
    "clouddesk_workflow_observation",
    default=None,
)


def bind_node_observation(observation: WorkflowNodeObservation) -> Token:
    return _current_observation.set(observation)


def reset_node_observation(token: Token) -> None:
    _current_observation.reset(token)


async def record_llm_call(
    *,
    schema_name: str,
    usage: Mapping[str, int],
    duration_ms: float,
    estimated_cost: float | None,
) -> None:
    observation = _current_observation.get()
    if observation is None:
        return
    await observation.record_llm_call(
        schema_name=schema_name,
        usage=usage,
        duration_ms=duration_ms,
        estimated_cost=estimated_cost,
    )


async def record_tool_call(
    *,
    tool_name: str,
    ok: bool,
    error_type: str | None,
    requires_approval: bool,
    result_summary: Mapping[str, Any] | None,
    duration_ms: float,
) -> None:
    observation = _current_observation.get()
    if observation is None:
        return
    await observation.record_tool_call(
        tool_name=tool_name,
        ok=ok,
        error_type=error_type,
        requires_approval=requires_approval,
        result_summary=result_summary,
        duration_ms=duration_ms,
    )


def elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


__all__ = [
    "WorkflowNodeObservation",
    "bind_node_observation",
    "elapsed_ms",
    "record_llm_call",
    "record_tool_call",
    "reset_node_observation",
    "summarize_tool_result",
]
