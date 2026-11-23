from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings
from backend.app.core.database import create_database_engine, create_tables
from backend.app.tools.registry import ToolRegistry


@dataclass
class SupportToolState:
    customers: dict[str, dict[str, Any]] = field(default_factory=dict)
    subscriptions: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    histories: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    statuses: dict[str, str] = field(
        default_factory=lambda: {
            "api": "operational",
            "authentication": "operational",
            "billing": "operational",
            "storage": "operational",
        }
    )
    escalations: list[dict[str, Any]] = field(default_factory=list)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
    await engine.dispose()


@pytest.fixture
def support_tool_state() -> SupportToolState:
    return SupportToolState()


@pytest.fixture
def tool_registry(support_tool_state: SupportToolState) -> ToolRegistry:
    state = support_tool_state

    @tool
    async def get_customer(customer_id: str) -> dict[str, Any] | None:
        """Return a customer profile from the test support data."""
        return state.customers.get(customer_id)

    @tool
    async def get_subscription(customer_id: str) -> list[dict[str, Any]]:
        """Return a customer's subscriptions from the test support data."""
        return state.subscriptions.get(customer_id, [])

    @tool
    async def get_ticket_history(
        customer_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return a customer's ticket history from the test support data."""
        return state.histories.get(customer_id, [])[:limit]

    @tool
    async def search_docs(
        query: str,
        category: str | None = None,
        mode: str = "hybrid",
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Return support evidence from the test support data."""
        return state.evidence[:top_k]

    @tool
    async def check_service_status(service_name: str) -> dict[str, str]:
        """Return a mock service status."""
        normalized = service_name.strip().casefold()
        return {
            "service": normalized,
            "status": state.statuses.get(normalized, "unknown"),
        }

    @tool
    async def create_escalation(
        ticket_id: str,
        team: str,
        reason: str,
        workflow_run_id: str | None = None,
    ) -> dict[str, Any]:
        """Record a mock escalation."""
        record = {
            "ticket_id": ticket_id,
            "team": team,
            "reason": reason,
            "workflow_run_id": workflow_run_id,
            "status": "open",
        }
        state.escalations.append(record)
        return record

    return ToolRegistry(
        [
            get_customer,
            get_subscription,
            get_ticket_history,
            search_docs,
            check_service_status,
            create_escalation,
        ],
        settings=Settings(_env_file=None),
    )
