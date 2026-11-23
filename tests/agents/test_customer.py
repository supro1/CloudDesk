from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from agents.specialists import CustomerAgent
from backend.app.models.entities import Customer
from backend.app.repositories import CustomerMemoryRepository
from backend.app.schemas.workflow import CustomerContext
from memory.long_term import LongTermMemory
from tests.agents.conftest import SupportToolState


async def test_customer_agent_combines_read_tools_and_customer_memory(
    session: AsyncSession,
    tool_registry,
    support_tool_state: SupportToolState,
) -> None:
    customer = Customer(name="Ada Lovelace", email="ada@example.test")
    other_customer = Customer(name="Grace Hopper", email="grace@example.test")
    session.add_all([customer, other_customer])
    await session.flush()
    support_tool_state.customers[customer.id] = {
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "workspaces": [],
    }
    support_tool_state.subscriptions[customer.id] = [
        {"plan_name": "business", "status": "active"}
    ]
    support_tool_state.histories[customer.id] = [
        {"ticket_number": "CD-1008", "status": "resolved"}
    ]
    memory = LongTermMemory(CustomerMemoryRepository(session))
    await memory.record_note(
        customer_id=customer.id,
        kind="preference",
        content="Prefers email updates.",
    )
    await memory.record_note(
        customer_id=other_customer.id,
        kind="note",
        content="This note belongs to a different customer.",
    )

    result = await CustomerAgent(tool_registry, memory).run(customer.id)

    assert isinstance(result, CustomerContext)
    assert result.customer is not None
    assert result.subscriptions[0]["plan_name"] == "business"
    assert result.previous_tickets[0]["ticket_number"] == "CD-1008"
    assert result.memory_notes[0].content == "Prefers email updates."
    assert all(
        note.content != "This note belongs to a different customer."
        for note in result.memory_notes
    )


async def test_customer_agent_keeps_missing_customer_context_empty(
    session: AsyncSession,
    tool_registry,
) -> None:
    result = await CustomerAgent(
        tool_registry,
        LongTermMemory(CustomerMemoryRepository(session)),
    ).run("missing-customer")

    assert result.customer is None
    assert result.subscriptions == []
    assert result.previous_tickets == []
    assert result.memory_notes == []
