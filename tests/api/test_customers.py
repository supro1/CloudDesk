from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables, get_session
from backend.app.main import create_app
from backend.app.models.entities import (
    Customer,
    CustomerMemory,
    Profile,
    Subscription,
    Ticket,
    Workspace,
)

VIEWER_ID = "00000000-0000-4000-8000-000000000003"
CUSTOMER_ID = "00000000-0000-4000-8000-000000000010"
OTHER_CUSTOMER_ID = "00000000-0000-4000-8000-000000000011"
SECOND_NORTHSTAR_CUSTOMER_ID = "00000000-0000-4000-8000-000000000012"


@pytest.fixture
async def customer_client() -> AsyncIterator[tuple[TestClient, async_sessionmaker[AsyncSession]]]:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add_all(
            [
                Profile(
                    id=VIEWER_ID,
                    email="vic.viewer@clouddesk.demo",
                    display_name="Vic Chen",
                    role="viewer",
                    is_active=True,
                ),
                Customer(
                    id=CUSTOMER_ID,
                    name="Maya Patel",
                    email="maya@example.test",
                    company_name="Northstar Health",
                ),
                Customer(
                    id=OTHER_CUSTOMER_ID,
                    name="Alex Chen",
                    email="alex@example.test",
                    company_name="Other Company",
                ),
                Customer(
                    id=SECOND_NORTHSTAR_CUSTOMER_ID,
                    name="Riley Shah",
                    email="riley@example.test",
                    company_name="Northstar Health",
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                    updated_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ]
        )
        await session.commit()

    app = create_app(
        Settings(
            _env_file=None,
            demo_mode=True,
            jwt_secret="test-jwt-secret-with-at-least-32-bytes",
        )
    )

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client, session_maker
    await engine.dispose()


def _viewer_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "vic.viewer@clouddesk.demo"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_customer_list_filters_and_paginates(
    customer_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = customer_client
    headers = _viewer_headers(client)

    response = client.get(
        "/api/v1/customers",
        headers=headers,
        params={"company_name": "Northstar Health", "limit": 1, "offset": 0},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["limit"] == 1
    assert response.json()["offset"] == 0
    assert response.json()["items"][0]["id"] == CUSTOMER_ID

    next_page = client.get(
        "/api/v1/customers",
        headers=headers,
        params={"company_name": "Northstar Health", "limit": 1, "offset": 1},
    )
    assert next_page.status_code == 200
    assert next_page.json()["total"] == 2
    assert next_page.json()["items"][0]["id"] == SECOND_NORTHSTAR_CUSTOMER_ID

    filtered = client.get(
        "/api/v1/customers",
        headers=headers,
        params={"email": "maya@example.test"},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [CUSTOMER_ID]

    unauthorized = client.get("/api/v1/customers")
    assert unauthorized.status_code == 401


async def test_customer_detail_returns_only_owned_related_records_and_20_tickets(
    customer_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_maker = customer_client
    now = datetime.now(UTC)
    async with session_maker() as session:
        session.add_all(
            [
                Subscription(
                    customer_id=CUSTOMER_ID,
                    plan_name="Business",
                    status="active",
                    seat_count=10,
                    seats_used=5,
                    storage_limit_bytes=5000,
                    storage_used_bytes=1000,
                    current_period_start=now,
                    current_period_end=now + timedelta(days=30),
                ),
                Workspace(
                    customer_id=CUSTOMER_ID,
                    name="Northstar",
                    slug="northstar",
                    settings={"sso_enabled": True},
                    is_active=True,
                ),
                Subscription(
                    customer_id=OTHER_CUSTOMER_ID,
                    plan_name="Other",
                    status="active",
                    seat_count=1,
                    seats_used=1,
                    storage_limit_bytes=100,
                    storage_used_bytes=10,
                ),
                Workspace(
                    customer_id=OTHER_CUSTOMER_ID,
                    name="Other workspace",
                    slug="other",
                    settings={},
                    is_active=True,
                ),
                CustomerMemory(
                    customer_id=CUSTOMER_ID,
                    kind="note",
                    content="private memory content",
                ),
                CustomerMemory(
                    customer_id=OTHER_CUSTOMER_ID,
                    kind="note",
                    content="other customer's private memory",
                ),
            ]
        )
        for index in range(21):
            session.add(
                Ticket(
                    ticket_number=f"CD-{1001 + index}",
                    customer_id=CUSTOMER_ID,
                    subject=f"Ticket {index}",
                    channel="web",
                    status="new",
                    created_at=now + timedelta(seconds=index),
                    updated_at=now + timedelta(seconds=index),
                )
            )
        session.add(
            Ticket(
                ticket_number="CD-2000",
                customer_id=OTHER_CUSTOMER_ID,
                subject="Other customer's ticket",
                channel="web",
                status="new",
            )
        )
        await session.commit()

    response = client.get(
        f"/api/v1/customers/{CUSTOMER_ID}",
        headers=_viewer_headers(client),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer"]["id"] == CUSTOMER_ID
    assert len(payload["subscriptions"]) == 1
    assert payload["subscriptions"][0]["plan_name"] == "Business"
    assert [workspace["slug"] for workspace in payload["workspaces"]] == ["northstar"]
    assert len(payload["recent_tickets"]) == 20
    assert payload["recent_tickets"][0]["ticket_number"] == "CD-1021"
    assert all(ticket["customer_id"] == CUSTOMER_ID for ticket in payload["recent_tickets"])
    assert "messages" not in payload["recent_tickets"][0]
    serialized = response.text
    assert "private memory content" not in serialized
    assert "other customer's private memory" not in serialized
    assert "Other workspace" not in serialized


def test_customer_detail_returns_404_for_unknown_customer(
    customer_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = customer_client
    response = client.get(
        "/api/v1/customers/00000000-0000-4000-8000-000000000099",
        headers=_viewer_headers(client),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Customer not found"}
