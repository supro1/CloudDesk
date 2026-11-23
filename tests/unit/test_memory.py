from __future__ import annotations

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import create_database_engine, create_tables
from backend.app.models.entities import Customer, Ticket
from backend.app.repositories import CustomerMemoryRepository
from memory.long_term import LongTermMemory
from memory.short_term import (
    RETRIEVAL_CACHE_TTL_SECONDS,
    SHORT_TERM_TTL_SECONDS,
    ShortTermMemory,
)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_database_engine("sqlite+aiosqlite:///:memory:")
    await create_tables(engine)
    async with AsyncSession(engine, expire_on_commit=False) as test_session:
        yield test_session
    await engine.dispose()


async def test_short_term_memory_scopes_data_and_applies_ttls() -> None:
    redis = FakeRedis()
    memory = ShortTermMemory(redis)
    conversation = [{"role": "customer", "content": "Login is unavailable"}]

    await memory.set_conversation("ticket-1", conversation)
    await memory.set_workflow_state("workflow-1", {"node": "investigate"})
    await memory.set_retrieval_cache(
        [{"article": "login-help"}],
        mode="hybrid",
        category="login_issue",
        top_k=3,
        query="cannot sign in",
    )

    assert await memory.get_conversation("ticket-1") == conversation
    assert await memory.get_conversation("ticket-2") is None
    assert await memory.get_workflow_state("workflow-1") == {"node": "investigate"}
    assert await memory.get_workflow_state("workflow-2") is None
    assert await memory.get_retrieval_cache(
        mode="hybrid",
        category="login_issue",
        top_k=3,
        query="cannot sign in",
    ) == [{"article": "login-help"}]
    assert await redis.ttl("memory:ticket:ticket-1:conversation") == SHORT_TERM_TTL_SECONDS
    assert await redis.ttl("memory:workflow:workflow-1:state") == SHORT_TERM_TTL_SECONDS
    assert (
        await redis.ttl("rag:hybrid:login_issue:3:cannot sign in")
        == RETRIEVAL_CACHE_TTL_SECONDS
    )
    await redis.aclose()


async def test_short_term_memory_rejects_malformed_stored_shapes() -> None:
    redis = FakeRedis()
    memory = ShortTermMemory(redis)
    await redis.set("memory:ticket:ticket-1:conversation", '{"not": "a list"}')
    await redis.set("memory:workflow:workflow-1:state", "[]")

    with pytest.raises(TypeError, match="conversation"):
        await memory.get_conversation("ticket-1")
    with pytest.raises(TypeError, match="workflow state"):
        await memory.get_workflow_state("workflow-1")
    await redis.aclose()


async def test_long_term_memory_scrubs_and_suppresses_customer_scoped_duplicates(
    session: AsyncSession,
) -> None:
    customer = Customer(name="Ada", email="ada@example.test")
    other_customer = Customer(name="Grace", email="grace@example.test")
    session.add_all([customer, other_customer])
    await session.flush()
    memory = LongTermMemory(CustomerMemoryRepository(session))

    first = await memory.record_note(
        customer_id=customer.id,
        kind="preference",
        content="Use api_key=sk-live-example in your integration",
    )
    duplicate = await memory.record_note(
        customer_id=customer.id,
        kind="preference",
        content="Use api_key=sk-live-example in your integration",
    )
    separate_customer = await memory.record_note(
        customer_id=other_customer.id,
        kind="preference",
        content=first.content,
    )

    assert first.content == "Use api_key=[REDACTED] in your integration"
    assert duplicate.id == first.id
    assert separate_customer.id != first.id
    assert await memory.recall_customer(customer.id) == [first]
    assert await memory.recall_customer(other_customer.id) == [separate_customer]


async def test_record_resolution_keeps_only_curated_notes_and_three_steps(
    session: AsyncSession,
) -> None:
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

    memory = LongTermMemory(CustomerMemoryRepository(session))
    records = await memory.record_resolution(
        customer_id=customer.id,
        source_ticket_id=ticket.id,
        ticket_body="I cannot sign in because password=secret123",
        summary="Customer could not sign in after a password reset.",
        troubleshooting_steps=[
            "Confirmed the account email.",
            "Reset the demo password.",
            "Asked the customer to retry sign-in.",
            "This fourth step must not be stored.",
        ],
        resolution="Access was restored after the password reset.",
    )

    assert [record.kind for record in records] == [
        "past_issue",
        "troubleshooting",
        "troubleshooting",
        "troubleshooting",
        "note",
    ]
    assert len(records) == 5
    assert all("secret123" not in record.content for record in records)
    assert all("fourth step" not in record.content for record in records)
    assert all(ticket.id == record.source_ticket_id for record in records)


async def test_long_term_memory_rejects_raw_ticket_and_prohibited_customer_text(
    session: AsyncSession,
) -> None:
    customer = Customer(name="Ada", email="ada@example.test")
    session.add(customer)
    await session.flush()
    ticket = Ticket(
        ticket_number="CD-1002",
        customer_id=customer.id,
        subject="Billing issue",
        channel="email",
    )
    session.add(ticket)
    await session.flush()
    memory = LongTermMemory(CustomerMemoryRepository(session))

    with pytest.raises(ValueError, match="Raw ticket text"):
        await memory.record_resolution(
            customer_id=customer.id,
            source_ticket_id=ticket.id,
            ticket_body="This exact full message must never become a note.",
            summary="This exact full message must never become a note.",
            troubleshooting_steps=[],
            resolution="A safe resolution note.",
        )
    with pytest.raises(ValueError, match="prohibited"):
        await memory.record_note(
            customer_id=customer.id,
            kind="note",
            content="Related account belongs to secret@example.test",
            forbidden_values=("secret@example.test",),
        )

    assert await CustomerMemoryRepository(session).list_for_customer(customer.id) == []


async def test_memory_validates_kinds_and_caps_recall_at_ten(
    session: AsyncSession,
) -> None:
    customer = Customer(name="Ada", email="ada@example.test")
    session.add(customer)
    await session.flush()
    memory = LongTermMemory(CustomerMemoryRepository(session))

    with pytest.raises(ValueError, match="Unsupported"):
        await memory.record_note(
            customer_id=customer.id,
            kind="ticket_body",
            content="This is not an allowed note.",
        )
    for index in range(11):
        await memory.record_note(
            customer_id=customer.id,
            kind="note",
            content=f"Resolution note number {index}.",
        )

    assert len(await memory.recall_customer(customer.id, limit=50)) == 10
    with pytest.raises(ValueError, match="limit"):
        await memory.recall_customer(customer.id, limit=0)


