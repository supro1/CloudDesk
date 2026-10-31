from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, TypeGuard

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_session
from backend.app.core.security import (
    ROLE_LEVELS,
    AuthenticatedUser,
    UserRole,
    get_current_user,
)
from backend.app.models.entities import Profile
from backend.app.repositories import ProfileRepository
from backend.app.schemas.auth import (
    AuthenticatedProfile,
    DemoLoginRequest,
    LoginResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
TOKEN_LIFETIME = timedelta(hours=8)
DEMO_EMAILS = frozenset(
    {
        "admin@clouddesk.demo",
        "sam.agent@clouddesk.demo",
        "vic.viewer@clouddesk.demo",
    }
)


def _is_user_role(role: str) -> TypeGuard[UserRole]:
    return role in ROLE_LEVELS


def _profile_response(profile: Profile) -> AuthenticatedProfile:
    return AuthenticatedProfile.model_validate(profile, from_attributes=True)


@router.post("/login", response_model=LoginResponse)
async def login(
    body: DemoLoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LoginResponse:
    settings = request.app.state.settings
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo authentication is disabled",
        )

    secret = settings.effective_jwt_secret
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT signing is not configured",
        )

    if body.email not in DEMO_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid demo credentials",
        )

    profile = await ProfileRepository(session).get_by_email(body.email)
    if profile is None or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid demo credentials",
        )

    role = profile.role
    if not _is_user_role(role):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid demo credentials",
        )
    now = datetime.now(UTC)
    expires_at = now + TOKEN_LIFETIME
    token = jwt.encode(
        {
            "sub": profile.id,
            "email": profile.email,
            "aud": "authenticated",
            "role": "authenticated",
            "app_metadata": {"role": role},
            "iat": now,
            "exp": expires_at,
        },
        secret,
        algorithm="HS256",
    )
    return LoginResponse(
        access_token=token,
        expires_in=int(TOKEN_LIFETIME.total_seconds()),
        user=_profile_response(profile),
    )


@router.get("/me", response_model=AuthenticatedProfile)
async def get_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticatedProfile:
    profile = await ProfileRepository(session).get(current_user.subject)
    if profile is None or not profile.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _profile_response(profile)
