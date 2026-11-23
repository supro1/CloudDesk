from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.models.entities import WorkflowEvent, WorkflowRun
from backend.app.schemas.workflow import (
    WorkflowEventPageResponse,
    WorkflowEventResponse,
    WorkflowResolutionPreview,
    WorkflowStartResponse,
    WorkflowStatusResponse,
)
from backend.app.services.workflow_service import (
    TicketNotFoundError,
    WorkflowConflictError,
    WorkflowService,
)

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


def _service(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


def _status_response(run: WorkflowRun) -> WorkflowStatusResponse:
    state = run.state
    classification = state.get("classification") or {}
    severity = state.get("severity_assessment") or {}
    knowledge = state.get("knowledge") or {}
    resolution_plan = state.get("resolution_plan") or {}
    resolution = (
        WorkflowResolutionPreview(
            summary=resolution_plan["summary"],
            customer_reply=resolution_plan["customer_reply"],
            output_valid=resolution_plan["output_valid"],
            output_issues=resolution_plan["output_issues"],
        )
        if resolution_plan
        else None
    )
    return WorkflowStatusResponse(
        workflow_id=run.id,
        status=run.status,
        current_node=state.get("current_node"),
        completed_nodes=state.get("completed_nodes", []),
        category=classification.get("category"),
        severity=severity.get("severity"),
        severity_reason=severity.get("reason"),
        summary=(state.get("ticket_summary") or {}).get("summary")
        or (resolution_plan.get("summary") if resolution_plan else None)
        or classification.get("summary"),
        risk_level=state.get("risk_level"),
        evidence=knowledge.get("evidence", []),
        diagnosis=state.get("diagnosis"),
        resolution=resolution,
        token_usage=run.token_usage,
        error=run.error,
    )


def _event_response(event: WorkflowEvent) -> WorkflowEventResponse:
    cost_available = event.payload.get("cost_available", False)
    return WorkflowEventResponse(
        id=event.id,
        event_type=event.event_type,
        node_name=event.node_name,
        tool_name=event.tool_name,
        payload=event.payload,
        duration_ms=event.duration_ms,
        input_tokens=event.input_tokens,
        output_tokens=event.output_tokens,
        estimated_cost=float(event.estimated_cost) if cost_available else None,
        created_at=event.created_at,
    )


@router.post(
    "/{ticket_id}/run",
    response_model=WorkflowStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_workflow(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
) -> WorkflowStartResponse:
    try:
        run = await _service(request).create_run(ticket_id)
    except TicketNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except WorkflowConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    background_tasks.add_task(_service(request).start_workflow, run.id)
    return WorkflowStartResponse(workflow_id=run.id, status="queued")


@router.get(
    "/{ticket_id}/workflow",
    response_model=WorkflowStatusResponse,
)
async def get_workflow(
    ticket_id: str,
    request: Request,
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
) -> WorkflowStatusResponse:
    ticket_run = await _service(request).get_latest_run(ticket_id)
    if ticket_run is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _status_response(ticket_run)


@router.get(
    "/{ticket_id}/events",
    response_model=WorkflowEventPageResponse,
)
async def get_workflow_events(
    ticket_id: str,
    request: Request,
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
) -> WorkflowEventPageResponse:
    service = _service(request)
    run = await service.get_latest_run(ticket_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    events = await service.list_events(run.id)
    return WorkflowEventPageResponse(
        items=[_event_response(event) for event in events],
        total=len(events),
    )


__all__ = ["router"]
