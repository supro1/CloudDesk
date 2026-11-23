from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories import ApprovalRequestRepository
from backend.app.schemas.approvals import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalPageResponse,
    ApprovalResponse,
)
from backend.app.services.workflow_service import (
    ApprovalConflictError,
    ApprovalNotFoundError,
    TicketNotFoundError,
    WorkflowService,
)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


def _service(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


@router.get("", response_model=ApprovalPageResponse)
async def list_approvals(
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApprovalPageResponse:
    repository = ApprovalRequestRepository(session)
    approvals = await repository.list_all(limit=limit, offset=offset)
    return ApprovalPageResponse(
        items=[ApprovalResponse.model_validate(approval) for approval in approvals],
        total=await repository.count(),
        limit=limit,
        offset=offset,
    )


async def _decide(
    approval_id: str,
    *,
    approved: bool,
    body: ApprovalDecisionRequest | None,
    request: Request,
    current_user: AuthenticatedUser,
) -> ApprovalDecisionResponse:
    try:
        approval, workflow = await _service(request).decide_approval(
            approval_id,
            approved=approved,
            reason=body.reason if body is not None else None,
            decided_by_id=current_user.subject,
        )
    except ApprovalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TicketNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ApprovalConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ApprovalDecisionResponse(
        approval=ApprovalResponse.model_validate(approval),
        workflow_status=workflow.status,
    )


@router.post("/{approval_id}/approve", response_model=ApprovalDecisionResponse)
async def approve(
    approval_id: str,
    request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
    body: ApprovalDecisionRequest | None = None,
) -> ApprovalDecisionResponse:
    return await _decide(
        approval_id,
        approved=True,
        body=body,
        request=request,
        current_user=current_user,
    )


@router.post("/{approval_id}/reject", response_model=ApprovalDecisionResponse)
async def reject(
    approval_id: str,
    request: Request,
    current_user: Annotated[AuthenticatedUser, Depends(require_role("agent"))],
    body: ApprovalDecisionRequest | None = None,
) -> ApprovalDecisionResponse:
    return await _decide(
        approval_id,
        approved=False,
        body=body,
        request=request,
        current_user=current_user,
    )


__all__ = ["router"]
