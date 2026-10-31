from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import create_database_engine, create_tables
from backend.app.models.entities import Customer, Ticket
from backend.app.repositories import (
    BaseRepository,
    CustomerRepository,
    SupportArticleRepository,
    TicketMessageRepository,
    TicketRepository,
)
from backend.app.schemas.common import TicketCategory


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
    await engine.dispose()


async def test_base_repository_crud_and_pagination(session: AsyncSession) -> None:
    repository = BaseRepository(session, Customer)
    ada = await repository.create(name="Ada Lovelace", email="ada@example.test")
    grace = await repository.create(name="Grace Hopper", email="grace@example.test")

    assert await repository.get(ada.id) is ada
    assert await repository.count() == 2
    assert {customer.id for customer in await repository.list(limit=1)} <= {
        ada.id,
        grace.id,
    }

    updated = await repository.update(ada.id, {"company_name": "Analytical Engines"})
    assert updated is not None
    assert updated.company_name == "Analytical Engines"
    assert await repository.delete(grace.id)
    assert not await repository.delete(grace.id)
    assert await repository.count() == 1


async def test_base_repository_rejects_invalid_pagination_and_protected_fields(
    session: AsyncSession,
) -> None:
    repository = BaseRepository(session, Customer)

    with pytest.raises(ValueError, match="limit"):
        await repository.list(limit=0)
    with pytest.raises(ValueError, match="offset"):
        await repository.list(offset=-1)
    with pytest.raises(ValueError, match="id"):
        await repository.update("missing", {"id": "replacement"})


async def test_customer_and_ticket_queries(session: AsyncSession) -> None:
    customers = CustomerRepository(session)
    customer = await customers.create(name="Ada", email="ada@example.test")
    tickets = TicketRepository(session)
    first = await tickets.create(
        ticket_number="CD-1001",
        customer_id=customer.id,
        subject="Login issue",
        channel="email",
        external_id="ext-1",
    )
    await tickets.create(
        ticket_number="CD-1002",
        customer_id=customer.id,
        subject="Billing question",
        channel="chat",
        status="resolved",
    )

    assert (await customers.list_by_email(customer.email)) == [customer]
    assert await tickets.get_by_ticket_number("CD-1001") is first
    assert await tickets.get_by_external_id("email", "ext-1") is first
    assert [ticket.ticket_number for ticket in await tickets.list_for_customer(customer.id)] == [
        "CD-1002",
        "CD-1001",
    ]
    assert [ticket.ticket_number for ticket in await tickets.list_by_status("resolved")] == [
        "CD-1002"
    ]


async def test_ticket_messages_are_returned_in_creation_order(session: AsyncSession) -> None:
    customer = Customer(name="Ada", email="ada@example.test")
    session.add(customer)
    await session.flush()
    ticket = Ticket(
        ticket_number="CD-1001",
        customer_id=customer.id,
        subject="Login issue",
        channel="email",
    )
    session.add(ticket)
    await session.flush()
    messages = TicketMessageRepository(session)
    first = await messages.create(
        ticket_id=ticket.id,
        sender_type="customer",
        body="I cannot log in",
    )
    second = await messages.create(
        ticket_id=ticket.id,
        sender_type="agent",
        body="We are investigating",
    )

    assert [message.id for message in await messages.list_for_ticket(ticket.id)] == [
        first.id,
        second.id,
    ]


async def test_articles_can_be_filtered_by_publication_and_category(
    session: AsyncSession,
) -> None:
    repository = SupportArticleRepository(session)
    published = await repository.create(
        slug="login-help",
        title="Login help",
        category=TicketCategory.LOGIN_ISSUE,
        content="Reset the password.",
    )
    await repository.create(
        slug="billing-draft",
        title="Billing draft",
        category=TicketCategory.BILLING,
        content="Draft",
        is_published=False,
    )

    assert await repository.get_by_slug("login-help") is published
    assert await repository.list_published(category=TicketCategory.LOGIN_ISSUE) == [published]
