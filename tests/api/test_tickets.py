from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables, get_session
from backend.app.main import create_app
from backend.app.models.entities import (
    ApprovalRequest,
    Customer,
    Profile,
    WorkflowRun,
)

AGENT_ID = "00000000-0000-4000-8000-000000000002"
VIEWER_ID = "00000000-0000-4000-8000-000000000003"
CUSTOMER_ID = "00000000-0000-4000-8000-000000000010"


@pytest.fixture
async def ticket_client() -> AsyncIterator[tuple[TestClient, async_sessionmaker[AsyncSession]]]:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        session.add_all(
            [
                Profile(
                    id=AGENT_ID,
                    email="sam.agent@clouddesk.demo",
                    display_name="Sam Rivera",
                    role="agent",
                    is_active=True,
                ),
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


def _token(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(client: TestClient, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(client, email)}"}


def _create_ticket(
    client: TestClient,
    headers: dict[str, str],
    *,
    subject: str = "Uploads fail",
    body: str = "Uploads are failing.",
    external_id: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "subject": subject,
            "body": body,
            "customer_id": CUSTOMER_ID,
            "channel": "web",
            "external_id": external_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_ticket_records_initial_customer_message(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    headers = _headers(client, "sam.agent@clouddesk.demo")

    response = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "subject": "Uploads fail",
            "body": "Uploads are failing.",
            "customer_id": CUSTOMER_ID,
            "channel": "web",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["ticket_number"] == "CD-1001"
    assert payload["status"] == "new"
    assert payload["category"] is None
    assert payload["severity"] is None
    assert payload["customer"] == {
        "id": CUSTOMER_ID,
        "name": "Maya Patel",
        "email": "maya@example.test",
        "company_name": "Northstar Health",
    }
    assert payload["messages"][0]["body"] == "Uploads are failing."
    assert payload["messages"][0]["sender_type"] == "customer"
    assert payload["messages"][0]["is_internal"] is False
    assert "workflow" not in payload
    assert "approval" not in payload


def test_create_ticket_rejects_missing_customer_and_duplicate_external_id(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    headers = _headers(client, "sam.agent@clouddesk.demo")
    invalid_customer = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "subject": "Unknown customer",
            "body": "Help",
            "customer_id": "00000000-0000-4000-8000-000000000099",
            "channel": "web",
        },
    )
    _create_ticket(client, headers, external_id="source-42")
    duplicate = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "subject": "Duplicate",
            "body": "Help",
            "customer_id": CUSTOMER_ID,
            "channel": "web",
            "external_id": "source-42",
        },
    )

    assert invalid_customer.status_code == 404
    assert duplicate.status_code == 409


def test_ticket_list_filters_and_paginates(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    agent_headers = _headers(client, "sam.agent@clouddesk.demo")
    viewer_headers = _headers(client, "vic.viewer@clouddesk.demo")
    first = _create_ticket(client, agent_headers, subject="First ticket")
    second = _create_ticket(client, agent_headers, subject="Second ticket")
    client.patch(
        f"/api/v1/tickets/{first['id']}",
        headers=agent_headers,
        json={"status": "resolved", "category": "billing"},
    )

    response = client.get(
        "/api/v1/tickets",
        headers=viewer_headers,
        params={"status": "resolved", "category": "billing", "limit": 1, "offset": 0},
    )
    page = response.json()

    assert response.status_code == 200
    assert page["total"] == 1
    assert page["limit"] == 1
    assert page["offset"] == 0
    assert [ticket["id"] for ticket in page["items"]] == [first["id"]]
    assert second["id"] != first["id"]


def test_ticket_detail_includes_messages_and_missing_ticket_is_404(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    headers = _headers(client, "vic.viewer@clouddesk.demo")
    created = _create_ticket(client, _headers(client, "sam.agent@clouddesk.demo"))

    response = client.get(f"/api/v1/tickets/{created['id']}", headers=headers)
    missing = client.get(
        "/api/v1/tickets/00000000-0000-4000-8000-000000000099",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["messages"][0]["ticket_id"] == created["id"]
    assert response.json()["customer"]["email"] == "maya@example.test"
    assert missing.status_code == 404


async def test_ticket_detail_includes_latest_workflow_and_approval_when_present(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_maker = ticket_client
    created = _create_ticket(client, _headers(client, "sam.agent@clouddesk.demo"))
    async with session_maker() as session:
        workflow = WorkflowRun(
            ticket_id=str(created["id"]),
            status="paused",
            state={},
        )
        session.add(workflow)
        await session.flush()
        session.add(
            ApprovalRequest(
                ticket_id=str(created["id"]),
                workflow_run_id=workflow.id,
                action="create_refund_request",
                summary="Review the refund request.",
                status="pending",
            )
        )
        await session.commit()

    response = client.get(
        f"/api/v1/tickets/{created['id']}",
        headers=_headers(client, "vic.viewer@clouddesk.demo"),
    )

    assert response.status_code == 200
    assert response.json()["workflow"]["status"] == "paused"
    assert response.json()["approval"]["workflow_id"] == workflow.id


def test_patch_ticket_only_updates_supported_fields_and_allows_clearing(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    headers = _headers(client, "sam.agent@clouddesk.demo")
    created = _create_ticket(client, headers)
    client.patch(
        f"/api/v1/tickets/{created['id']}",
        headers=headers,
        json={
            "status": "resolved",
            "category": "billing",
            "severity": "medium",
            "severity_reason": "Customer impact is limited.",
            "summary": "Billing issue",
        },
    )

    response = client.patch(
        f"/api/v1/tickets/{created['id']}",
        headers=headers,
        json={"category": None, "severity": None, "summary": None},
    )
    empty = client.patch(
        f"/api/v1/tickets/{created['id']}",
        headers=headers,
        json={},
    )
    unsupported = client.patch(
        f"/api/v1/tickets/{created['id']}",
        headers=headers,
        json={"customer_id": CUSTOMER_ID},
    )
    null_status = client.patch(
        f"/api/v1/tickets/{created['id']}",
        headers=headers,
        json={"status": None},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert response.json()["category"] is None
    assert response.json()["severity"] is None
    assert response.json()["summary"] is None
    assert empty.status_code == 422
    assert unsupported.status_code == 422
    assert null_status.status_code == 422


def test_ticket_routes_require_authentication_and_agent_role_for_writes(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    viewer_headers = _headers(client, "vic.viewer@clouddesk.demo")

    no_auth = client.get("/api/v1/tickets")
    forbidden = client.post(
        "/api/v1/tickets",
        headers=viewer_headers,
        json={
            "subject": "Uploads fail",
            "body": "Help",
            "customer_id": CUSTOMER_ID,
            "channel": "web",
        },
    )

    assert no_auth.status_code == 401
    assert forbidden.status_code == 403
