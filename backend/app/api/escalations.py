from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import AuthenticatedUser, require_role
from backend.app.repositories import EscalationRepository
from backend.app.schemas.escalations import (
    EscalationPageResponse,
    EscalationResponse,
)

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])


@router.get("", response_model=EscalationPageResponse)
async def list_escalations(
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: str | None = Query(default=None, alias="status"),
    team: str | None = None,
    ticket_id: UUID | None = None,
) -> EscalationPageResponse:
    repository = EscalationRepository(session)
    filters = {
        "status": status_filter,
        "team": team,
        "ticket_id": str(ticket_id) if ticket_id is not None else None,
    }
    records = await repository.list_filtered(
        limit=limit,
        offset=offset,
        **filters,
    )
    return EscalationPageResponse(
        items=[EscalationResponse.model_validate(record) for record in records],
        total=await repository.count_filtered(**filters),
        limit=limit,
        offset=offset,
    )


@router.get("/{escalation_id}", response_model=EscalationResponse)
async def get_escalation(
    escalation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _current_user: Annotated[AuthenticatedUser, Depends(require_role("viewer"))],
) -> EscalationResponse:
    record = await EscalationRepository(session).get(escalation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return EscalationResponse.model_validate(record)


__all__ = ["router"]
