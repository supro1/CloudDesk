from __future__ import annotations

from collections.abc import AsyncIterator

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables, get_session
from backend.app.main import create_app
from backend.app.models.entities import Profile

JWT_SECRET = "test-jwt-secret-with-at-least-32-bytes"


@pytest.fixture
async def auth_client() -> AsyncIterator[tuple[TestClient, Settings]]:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add_all(
            [
                Profile(
                    id="00000000-0000-4000-8000-000000000001",
                    email="admin@clouddesk.demo",
                    display_name="CloudDesk Admin",
                    role="admin",
                    is_active=True,
                ),
                Profile(
                    id="00000000-0000-4000-8000-000000000002",
                    email="sam.agent@clouddesk.demo",
                    display_name="Sam Rivera",
                    role="agent",
                    is_active=True,
                ),
                Profile(
                    id="00000000-0000-4000-8000-000000000003",
                    email="vic.viewer@clouddesk.demo",
                    display_name="Vic Chen",
                    role="viewer",
                    is_active=True,
                ),
            ]
        )
        await session.commit()

    settings = Settings(
        _env_file=None,
        demo_mode=True,
        jwt_secret=JWT_SECRET,
    )
    app = create_app(settings)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client, settings
    await engine.dispose()


@pytest.mark.parametrize(
    ("email", "role", "display_name", "user_id"),
    [
        (
            "admin@clouddesk.demo",
            "admin",
            "CloudDesk Admin",
            "00000000-0000-4000-8000-000000000001",
        ),
        (
            "sam.agent@clouddesk.demo",
            "agent",
            "Sam Rivera",
            "00000000-0000-4000-8000-000000000002",
        ),
        (
            "vic.viewer@clouddesk.demo",
            "viewer",
            "Vic Chen",
            "00000000-0000-4000-8000-000000000003",
        ),
    ],
)
def test_demo_login_returns_profile_and_eight_hour_supabase_compatible_token(
    auth_client: tuple[TestClient, Settings],
    email: str,
    role: str,
    display_name: str,
    user_id: str,
) -> None:
    client, _ = auth_client
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f" {email.upper()} "},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 28800
    assert payload["user"] == {
        "id": user_id,
        "email": email,
        "role": role,
        "display_name": display_name,
    }

    claims = jwt.decode(
        payload["access_token"],
        JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert claims["sub"] == payload["user"]["id"]
    assert claims["role"] == "authenticated"
    assert claims["app_metadata"] == {"role": role}
    assert claims["exp"] - claims["iat"] == 28800

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json() == payload["user"]


@pytest.mark.parametrize(
    ("email", "status_code"),
    [
        ("someone@example.com", 401),
        ("", 422),
    ],
)
def test_demo_login_rejects_unknown_or_invalid_email(
    auth_client: tuple[TestClient, Settings],
    email: str,
    status_code: int,
) -> None:
    client, _ = auth_client

    response = client.post("/api/v1/auth/login", json={"email": email})

    assert response.status_code == status_code


def test_demo_login_is_disabled_outside_demo_mode(
    auth_client: tuple[TestClient, Settings],
) -> None:
    client, settings = auth_client
    settings.demo_mode = False

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@clouddesk.demo"},
    )

    assert response.status_code == 403


def test_demo_login_requires_a_configured_signing_secret(
    auth_client: tuple[TestClient, Settings],
) -> None:
    client, settings = auth_client
    settings.jwt_secret = None

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@clouddesk.demo"},
    )

    assert response.status_code == 503


def test_current_user_requires_a_valid_bearer_token(
    auth_client: tuple[TestClient, Settings],
) -> None:
    client, _ = auth_client

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
