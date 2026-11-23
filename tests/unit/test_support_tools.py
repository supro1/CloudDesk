from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables
from backend.app.models.entities import (
    Customer,
    Subscription,
    SupportArticle,
    Ticket,
    Workspace,
)
from backend.app.repositories import EscalationRepository
from backend.app.services.knowledge_service import KnowledgeService
from backend.app.tools.factory import create_support_tool_registry
from backend.app.tools.registry import ToolRegistry
from integrations import SupportIntegrations, create_mock_integrations
from integrations.mock.services import (
    MockBillingIntegration,
    MockServiceStatusIntegration,
    MockWorkspaceIntegration,
)
from rag.embeddings import FakeEmbeddings
from rag.vector_store import InMemoryVectorStore


@pytest.fixture
async def tool_context() -> AsyncIterator[
    tuple[
        ToolRegistry,
        async_sessionmaker[AsyncSession],
        KnowledgeService,
        SupportIntegrations,
    ]
]:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    knowledge_service = KnowledgeService(
        InMemoryVectorStore(),
        FakeEmbeddings(),
    )
    integrations = create_mock_integrations()

    async with session_factory() as session:
        customer = Customer(name="Ada Lovelace", email="ada@example.test")
        session.add(customer)
        await session.flush()
        workspace = Workspace(
            customer_id=customer.id,
            name="Analytical Engines",
            slug="analytical-engines",
        )
        session.add_all(
            [
                workspace,
                Subscription(
                    customer_id=customer.id,
                    plan_name="business",
                    seat_count=10,
                    seats_used=5,
                    storage_limit_bytes=1_000,
                    storage_used_bytes=250,
                ),
                Ticket(
                    ticket_number="CD-1001",
                    customer_id=customer.id,
                    subject="Refund question",
                    channel="email",
                    summary="Customer has a billing question.",
                ),
                SupportArticle(
                    slug="billing-refund",
                    title="Refund requests",
                    content="Refund requests are reviewed by the billing team.",
                ),
            ]
        )
        await session.commit()

    settings = Settings(_env_file=None)
    registry = create_support_tool_registry(
        session_factory,
        knowledge_service,
        integrations=integrations,
        settings=settings,
    )
    yield registry, session_factory, knowledge_service, integrations
    await knowledge_service.close()
    await engine.dispose()


async def test_read_tools_return_customer_subscription_history_and_citations(
    tool_context: tuple[
        ToolRegistry,
        async_sessionmaker[AsyncSession],
        KnowledgeService,
        SupportIntegrations,
    ],
) -> None:
    registry, session_factory, _, _ = tool_context
    async with session_factory() as session:
        customer = await session.scalar(select(Customer))
        assert customer is not None

    customer_result = await registry.execute(
        "get_customer", {"customer_id": customer.id}
    )
    subscription_result = await registry.execute(
        "get_subscription", {"customer_id": customer.id}
    )
    history_result = await registry.execute(
        "get_ticket_history", {"customer_id": customer.id}
    )
    search_result = await registry.execute(
        "search_docs",
        {"query": "refund billing request", "mode": "keyword", "top_k": 1},
    )
    status_result = await registry.execute(
        "check_service_status", {"service_name": "billing"}
    )

    assert customer_result.ok
    assert customer_result.result["workspaces"][0]["name"] == "Analytical Engines"
    assert subscription_result.result[0]["plan_name"] == "business"
    assert history_result.result[0]["ticket_number"] == "CD-1001"
    assert search_result.ok
    assert search_result.result[0]["source"].startswith("kb://billing-refund")
    assert status_result.result["status"] == "operational"


async def test_refund_and_workspace_writes_require_registry_approval(
    tool_context: tuple[
        ToolRegistry,
        async_sessionmaker[AsyncSession],
        KnowledgeService,
        SupportIntegrations,
    ],
) -> None:
    registry, session_factory, _, integrations = tool_context
    async with session_factory() as session:
        ticket = await session.scalar(select(Ticket))
        workspace = await session.scalar(select(Workspace))
        assert ticket is not None and workspace is not None

    refund_args = {
        "ticket_id": ticket.id,
        "customer_id": ticket.customer_id,
        "amount": "19.95",
        "reason": "Duplicate seat charge",
    }
    blocked_refund = await registry.execute(
        "create_refund_request", refund_args
    )
    assert not blocked_refund.ok
    assert blocked_refund.requires_approval
    assert not integrations.billing.refund_requests

    approved_refund = await registry.execute(
        "create_refund_request", refund_args, approved=True
    )
    assert approved_refund.ok
    assert approved_refund.result["amount"] == "19.95"
    assert approved_refund.result["mock"] is True
    assert integrations.billing.refund_requests

    reset_args = {
        "workspace_id": workspace.id,
        "setting_name": "sso",
    }
    blocked_reset = await registry.execute("reset_demo_setting", reset_args)
    assert not blocked_reset.ok
    assert blocked_reset.requires_approval
    assert not integrations.workspace.settings

    approved_reset = await registry.execute(
        "reset_demo_setting", reset_args, approved=True
    )
    assert approved_reset.ok
    assert approved_reset.result["mock"] is True
    assert integrations.workspace.settings[(workspace.id, "sso")] is True


async def test_safe_ticket_updates_and_escalations_use_persisted_repositories(
    tool_context: tuple[
        ToolRegistry,
        async_sessionmaker[AsyncSession],
        KnowledgeService,
        SupportIntegrations,
    ],
) -> None:
    registry, session_factory, _, _ = tool_context
    async with session_factory() as session:
        ticket = await session.scalar(select(Ticket))
        assert ticket is not None
        ticket_id = ticket.id

    updated = await registry.execute(
        "update_ticket",
        {"ticket_id": ticket_id, "status": "in_progress"},
    )
    escalation = await registry.execute(
        "create_escalation",
        {
            "ticket_id": ticket_id,
            "team": "Billing",
            "reason": "Charge requires specialist review.",
        },
    )

    assert updated.ok
    assert updated.result["status"] == "in_progress"
    assert escalation.ok
    assert escalation.result["team"] == "Billing"
    async with session_factory() as session:
        records = await EscalationRepository(session).list_for_ticket(ticket_id)
        assert len(records) == 1
        assert records[0].reason == "Charge requires specialist review."


async def test_mock_integration_contracts_are_explicit_and_never_issue_refunds() -> None:
    billing = MockBillingIntegration()
    workspace = MockWorkspaceIntegration()
    status = MockServiceStatusIntegration()

    request = await billing.create_refund_request(
        ticket_id="ticket-1",
        customer_id="customer-1",
        amount=Decimal("3.50"),
        reason="test",
    )
    reset = await workspace.reset_setting(
        workspace_id="workspace-1",
        setting_name="sso",
    )
    unknown_status = await status.check_service_status("unknown-service")

    assert request["status"] == "request_created"
    assert request["mock"] is True
    assert "no money was moved" in str(request["message"])
    assert reset["mock"] is True
    assert unknown_status["status"] == "unknown"
