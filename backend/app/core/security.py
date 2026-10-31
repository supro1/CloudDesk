from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Literal

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.app.core.config import Settings

UserRole = Literal["viewer", "agent", "admin"]

ROLE_LEVELS: dict[UserRole, int] = {"viewer": 1, "agent": 2, "admin": 3}

_bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    subject: str
    role: UserRole
    email: str | None = None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _role_from_claims(claims: Mapping[str, object]) -> UserRole:
    app_metadata = claims.get("app_metadata")
    role: object = (
        app_metadata.get("role")
        if isinstance(app_metadata, Mapping)
        else None
    )
    if role is None:
        role = claims.get("user_role")
    if role is None:
        role = claims.get("role")

    if not isinstance(role, str) or role not in ROLE_LEVELS:
        raise _unauthorized()
    return role


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    settings: Settings = request.app.state.settings
    secret = settings.effective_jwt_secret
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT verification is not configured",
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
    except jwt.InvalidTokenError as error:
        raise _unauthorized() from error

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise _unauthorized()

    request.state.actor_id = subject
    email = claims.get("email")
    return AuthenticatedUser(
        subject=subject,
        role=_role_from_claims(claims),
        email=email if isinstance(email, str) else None,
    )


def require_role(
    minimum_role: UserRole,
) -> Callable[..., Awaitable[AuthenticatedUser]]:
    async def role_checker(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if ROLE_LEVELS[current_user.role] < ROLE_LEVELS[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker
