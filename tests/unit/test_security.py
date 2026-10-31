from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.app.core.config import Settings
from backend.app.core.security import (
    AuthenticatedUser,
    UserRole,
    get_current_user,
    require_role,
)

JWT_SECRET = "test-jwt-secret-with-at-least-32-bytes"


def make_request(settings: Settings) -> Request:
    app = SimpleNamespace(state=SimpleNamespace(settings=settings))
    return Request({"type": "http", "app": app, "headers": []})


def make_token(
    claims: dict[str, object] | None = None,
    *,
    secret: str = JWT_SECRET,
) -> str:
    payload: dict[str, object] = {
        "sub": "user-123",
        "role": "agent",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def authenticate(token: str, settings: Settings | None = None) -> AuthenticatedUser:
    request = make_request(
        settings or Settings(jwt_secret=JWT_SECRET, _env_file=None)
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return asyncio.run(get_current_user(request, credentials))


def test_valid_jwt_returns_authenticated_user() -> None:
    user = authenticate(make_token({"email": "agent@clouddesk.demo"}))

    assert user.subject == "user-123"
    assert user.role == "agent"
    assert user.email == "agent@clouddesk.demo"


def test_supabase_app_metadata_role_is_used() -> None:
    user = authenticate(
        make_token(
            {
                "role": "authenticated",
                "app_metadata": {"role": "admin"},
                "aud": "authenticated",
            }
        )
    )

    assert user.role == "admin"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        make_token(
            {"exp": datetime.now(UTC) - timedelta(minutes=1)}
        ),
        make_token(secret="different-secret-with-at-least-32-bytes"),
        make_token({"role": "authenticated"}),
    ],
)
def test_invalid_expired_or_roleless_jwt_is_rejected(token: str) -> None:
    with pytest.raises(HTTPException) as error:
        authenticate(token)

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_jwt_without_configured_secret_returns_service_unavailable() -> None:
    with pytest.raises(HTTPException) as error:
        authenticate(make_token(), Settings(_env_file=None))

    assert error.value.status_code == 503


@pytest.mark.parametrize(
    "credentials",
    [
        None,
        HTTPAuthorizationCredentials(scheme="Basic", credentials="not-a-jwt"),
    ],
)
def test_missing_or_non_bearer_credentials_are_rejected(
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    request = make_request(Settings(jwt_secret=JWT_SECRET, _env_file=None))

    with pytest.raises(HTTPException) as error:
        asyncio.run(get_current_user(request, credentials))

    assert error.value.status_code == 401


@pytest.mark.parametrize(
    ("role", "minimum_role", "allowed"),
    [
        ("viewer", "viewer", True),
        ("viewer", "agent", False),
        ("agent", "viewer", True),
        ("agent", "admin", False),
        ("admin", "admin", True),
    ],
)
def test_require_role_enforces_role_hierarchy(
    role: UserRole, minimum_role: UserRole, allowed: bool
) -> None:
    user = AuthenticatedUser(subject="user-123", role=role)
    guard = require_role(minimum_role)

    if allowed:
        assert asyncio.run(guard(user)) == user
    else:
        with pytest.raises(HTTPException) as error:
            asyncio.run(guard(user))
        assert error.value.status_code == 403


def test_require_role_is_enforced_by_fastapi_dependency() -> None:
    app = FastAPI()
    app.state.settings = Settings(jwt_secret=JWT_SECRET, _env_file=None)

    @app.get("/protected")
    async def protected(
        user: AuthenticatedUser = Depends(require_role("agent")),
    ) -> dict[str, str]:
        return {"subject": user.subject}

    client = TestClient(app)
    viewer_token = make_token({"role": "viewer"})
    agent_token = make_token({"role": "agent"})

    viewer_response = client.get(
        "/protected", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    agent_response = client.get(
        "/protected", headers={"Authorization": f"Bearer {agent_token}"}
    )
    missing_response = client.get("/protected")

    assert viewer_response.status_code == 403
    assert agent_response.status_code == 200
    assert agent_response.json() == {"subject": "user-123"}
    assert missing_response.status_code == 401
