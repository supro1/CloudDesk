from __future__ import annotations

from collections.abc import Callable

from langchain_core.tools import BaseTool, tool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.repositories import (
    CustomerRepository,
    SupportArticleRepository,
    SubscriptionRepository,
    TicketRepository,
    WorkspaceRepository,
)
from backend.app.schemas.common import TicketCategory
from backend.app.services.knowledge_service import KnowledgeService
from integrations.protocols import ServiceStatusIntegration
from rag.retriever import RetrievalMode

SessionFactory = async_sessionmaker[AsyncSession]


def create_read_only_tools(
    session_factory: SessionFactory,
    knowledge_service: KnowledgeService,
    service_status: ServiceStatusIntegration,
) -> list[BaseTool]:
    @tool
    async def get_customer(customer_id: str) -> dict[str, object] | None:
        """Read a customer's basic profile and workspace names and active states."""
        async with session_factory() as session:
            customer = await CustomerRepository(session).get(customer_id)
            if customer is None:
                return None
            workspaces = await WorkspaceRepository(session).list_for_customer(customer.id)
            return {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "company_name": customer.company_name,
                "workspaces": [
                    {
                        "id": workspace.id,
                        "name": workspace.name,
                        "slug": workspace.slug,
                        "is_active": workspace.is_active,
                    }
                    for workspace in workspaces
                ],
            }

    @tool
    async def get_subscription(customer_id: str) -> list[dict[str, object]]:
        """Read subscription plans and usage for a customer ID."""
        async with session_factory() as session:
            subscriptions = await SubscriptionRepository(session).list_for_customer(
                customer_id
            )
            return [
                {
                    "id": subscription.id,
                    "customer_id": subscription.customer_id,
                    "plan_name": subscription.plan_name,
                    "status": subscription.status,
                    "seat_count": subscription.seat_count,
                    "seats_used": subscription.seats_used,
                    "storage_limit_bytes": subscription.storage_limit_bytes,
                    "storage_used_bytes": subscription.storage_used_bytes,
                    "current_period_start": _to_iso(subscription.current_period_start),
                    "current_period_end": _to_iso(subscription.current_period_end),
                }
                for subscription in subscriptions
            ]

    @tool
    async def get_ticket_history(
        customer_id: str,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """Read a customer's recent support tickets without changing them."""
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        async with session_factory() as session:
            tickets = await TicketRepository(session).list_for_customer(
                customer_id,
                limit=limit,
            )
            return [
                {
                    "id": ticket.id,
                    "ticket_number": ticket.ticket_number,
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "category": _enum_value(ticket.category),
                    "severity": ticket.severity,
                    "summary": ticket.summary,
                    "created_at": _to_iso(ticket.created_at),
                }
                for ticket in tickets
            ]

    @tool
    async def search_docs(
        query: str,
        category: TicketCategory | None = None,
        mode: RetrievalMode = "hybrid",
        top_k: int = 3,
    ) -> list[dict[str, str | float]]:
        """Search published support articles and return passages with citations."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        async with session_factory() as session:
            articles = await SupportArticleRepository(session).list_published(
                limit=10_000
            )
            evidence = await knowledge_service.search(
                articles,
                query,
                category=category,
                mode=mode,
                top_k=top_k,
            )
            return [item.as_dict() for item in evidence]

    @tool
    async def check_service_status(service_name: str) -> dict[str, object]:
        """Read the simulated operational status of a CloudDesk service."""
        return dict(await service_status.check_service_status(service_name))

    return [
        get_customer,
        get_subscription,
        get_ticket_history,
        search_docs,
        check_service_status,
    ]


def _enum_value(value: object) -> str | None:
    return str(getattr(value, "value", value)) if value is not None else None


def _to_iso(value: object) -> str | None:
    isoformat: Callable[[], str] | None = getattr(value, "isoformat", None)
    return isoformat() if isoformat is not None else None
