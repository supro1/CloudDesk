from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables
from backend.app.main import create_app
from backend.app.models.entities import (
    ApprovalRequest,
    Customer,
    Profile,
    WorkflowRun,
)
from backend.app.repositories import (
    EscalationRepository,
    ResolutionActionRepository,
    WorkflowRunRepository,
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

    with TestClient(
        create_app(
            Settings(
                _env_file=None,
                demo_mode=True,
                jwt_secret="test-jwt-secret-with-at-least-32-bytes",
                checkpoint_db_path=":memory:",
            ),
            database_session_factory=session_maker,
        )
    ) as client:
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


def test_workflow_run_persists_progress_and_safe_events(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    agent_headers = _headers(client, "sam.agent@clouddesk.demo")
    viewer_headers = _headers(client, "vic.viewer@clouddesk.demo")
    created = _create_ticket(client, agent_headers)

    started = client.post(
        f"/api/v1/tickets/{created['id']}/run",
        headers=agent_headers,
    )
    workflow = client.get(
        f"/api/v1/tickets/{created['id']}/workflow",
        headers=viewer_headers,
    )
    events = client.get(
        f"/api/v1/tickets/{created['id']}/events",
        headers=viewer_headers,
    )

    assert started.status_code == 202, started.text
    assert started.json()["status"] == "queued"
    assert workflow.status_code == 200, workflow.text
    workflow_data = workflow.json()
    assert workflow_data["status"] == "completed"
    assert workflow_data["category"] == "storage_quota"
    assert workflow_data["completed_nodes"][-1] == "memory_update"
    assert "customer_reply" in workflow_data["resolution"]
    assert events.status_code == 200, events.text
    event_data = events.json()
    assert event_data["total"] > 0
    assert any(item["event_type"] == "llm_called" for item in event_data["items"])
    assert any(item["event_type"] == "tool_called" for item in event_data["items"])
    tool_events = [
        item for item in event_data["items"] if item["event_type"] == "tool_called"
    ]
    assert any(item["payload"]["result_summary"] is not None for item in tool_events)
    assert all(
        "prompt" not in str(item["payload"]).casefold()
        and "arguments" not in str(item["payload"]).casefold()
        for item in event_data["items"]
    )
    serialized_events = str(event_data).casefold()
    assert "maya@example.test" not in serialized_events
    assert "uploads are failing." not in serialized_events


def test_workflow_routes_enforce_agent_and_viewer_permissions(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = ticket_client
    created = _create_ticket(
        client,
        _headers(client, "sam.agent@clouddesk.demo"),
    )
    viewer_headers = _headers(client, "vic.viewer@clouddesk.demo")

    forbidden = client.post(
        f"/api/v1/tickets/{created['id']}/run",
        headers=viewer_headers,
    )
    missing = client.get(
        f"/api/v1/tickets/{created['id']}/workflow",
        headers=viewer_headers,
    )

    assert forbidden.status_code == 403
    assert missing.status_code == 404


async def test_refund_workflow_pauses_for_approval_then_uses_registry(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_maker = ticket_client
    agent_headers = _headers(client, "sam.agent@clouddesk.demo")
    viewer_headers = _headers(client, "vic.viewer@clouddesk.demo")
    created = _create_ticket(
        client,
        agent_headers,
        subject="Refund review for unused seats",
        body="Please review a $12.50 refund for the unused seats.",
    )

    started = client.post(
        f"/api/v1/tickets/{created['id']}/run",
        headers=agent_headers,
    )
    workflow = client.get(
        f"/api/v1/tickets/{created['id']}/workflow",
        headers=viewer_headers,
    )
    approvals = client.get("/api/v1/approvals", headers=agent_headers)
    approval = approvals.json()["items"][0]
    forbidden = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=viewer_headers,
    )
    approved = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=agent_headers,
        json={"reason": "Invoice amount checked."},
    )

    assert started.status_code == 202
    assert workflow.json()["status"] == "paused"
    assert workflow.json()["current_node"] == "human_approval"
    assert workflow.json()["risk_level"] == "high"
    assert approvals.status_code == 200
    assert approval["action"] == "create_refund_request"
    assert approval["status"] == "pending"
    assert forbidden.status_code == 403
    escalation_page = client.get(
        "/api/v1/escalations",
        headers=viewer_headers,
        params={"team": "billing", "ticket_id": created["id"]},
    )
    assert escalation_page.status_code == 200
    assert escalation_page.json()["total"] == 0
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval"]["status"] == "approved"
    assert approved.json()["approval"]["decided_by"] == AGENT_ID
    assert approved.json()["workflow_status"] == "completed"

    async with session_maker() as session:
        run = await WorkflowRunRepository(session).get(str(started.json()["workflow_id"]))
        assert run is not None
        actions = await ResolutionActionRepository(session).list_for_run(run.id)
    refund_action = next(action for action in actions if action.action_type == "create_refund_request")
    assert refund_action.status == "completed"
    assert refund_action.approval_required is True
    assert refund_action.result["amount"] == "12.50"
    duplicate_decision = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=agent_headers,
    )
    assert duplicate_decision.status_code == 409


async def test_rejected_approval_routes_to_billing_escalation_without_action(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_maker = ticket_client
    agent_headers = _headers(client, "sam.agent@clouddesk.demo")
    created = _create_ticket(
        client,
        agent_headers,
        subject="Refund review",
        body="Please review a $12.50 refund.",
    )
    started = client.post(
        f"/api/v1/tickets/{created['id']}/run",
        headers=agent_headers,
    )
    approvals = client.get("/api/v1/approvals", headers=agent_headers).json()["items"]

    rejected = client.post(
        f"/api/v1/approvals/{approvals[0]['id']}/reject",
        headers=agent_headers,
        json={"reason": "The invoice evidence is incomplete."},
    )
    workflow = client.get(
        f"/api/v1/tickets/{created['id']}/workflow",
        headers=agent_headers,
    )
    detail = client.get(
        f"/api/v1/tickets/{created['id']}",
        headers=agent_headers,
    )

    assert started.status_code == 202
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["approval"]["status"] == "rejected"
    assert rejected.json()["workflow_status"] == "completed"
    assert workflow.json()["completed_nodes"][-2:] == ["ticket_summary", "memory_update"]
    assert detail.json()["status"] == "escalated"
    async with session_maker() as session:
        escalations = await EscalationRepository(session).list_for_ticket(
            str(created["id"])
        )
        runs = await WorkflowRunRepository(session).list_for_ticket(str(created["id"]))
        actions = await ResolutionActionRepository(session).list_for_run(runs[0].id)
    assert escalations[0].team == "billing"
    assert actions == []


async def test_security_ticket_routes_to_named_team_and_updates_ticket(
    ticket_client: tuple[TestClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, session_maker = ticket_client
    agent_headers = _headers(client, "sam.agent@clouddesk.demo")
    created = _create_ticket(
        client,
        agent_headers,
        subject="Suspicious logins, possible breach",
        body="We see suspicious logins from unknown locations.",
    )

    started = client.post(
        f"/api/v1/tickets/{created['id']}/run",
        headers=agent_headers,
    )
    workflow = client.get(
        f"/api/v1/tickets/{created['id']}/workflow",
        headers=agent_headers,
    )
    async with session_maker() as session:
        escalations = await EscalationRepository(session).list_for_ticket(
            str(created["id"])
        )

    assert started.status_code == 202
    assert workflow.json()["status"] == "completed"
    assert workflow.json()["completed_nodes"][-3:] == [
        "escalation",
        "ticket_summary",
        "memory_update",
    ]
    assert len(escalations) == 1
    assert escalations[0].team == "security"
