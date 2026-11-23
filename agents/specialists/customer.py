from __future__ import annotations

import asyncio

from agents.specialists._tools import execute_tool
from backend.app.schemas.workflow import CustomerContext, CustomerMemoryNote
from backend.app.tools.registry import ToolRegistry
from memory.long_term import LongTermMemory


class CustomerAgent:
    """Load account context using allow-listed read tools and customer memory."""

    def __init__(
        self,
        tools: ToolRegistry,
        memory: LongTermMemory,
    ) -> None:
        self.tools = tools
        self.memory = memory

    async def run(
        self,
        customer_id: str,
        *,
        history_limit: int = 10,
        memory_limit: int = 10,
    ) -> CustomerContext:
        if not 1 <= history_limit <= 50:
            raise ValueError("history_limit must be between 1 and 50")

        customer, subscriptions, previous_tickets, memory_rows = await asyncio.gather(
            execute_tool(
                self.tools,
                "get_customer",
                {"customer_id": customer_id},
            ),
            execute_tool(
                self.tools,
                "get_subscription",
                {"customer_id": customer_id},
            ),
            execute_tool(
                self.tools,
                "get_ticket_history",
                {"customer_id": customer_id, "limit": history_limit},
            ),
            self.memory.recall_customer(customer_id, limit=memory_limit),
        )
        memory_notes = [
            CustomerMemoryNote(
                kind=row.kind,
                content=row.content,
                source_ticket_id=row.source_ticket_id,
            )
            for row in memory_rows
        ]
        return CustomerContext(
            customer=customer,
            subscriptions=subscriptions,
            previous_tickets=previous_tickets,
            memory_notes=memory_notes,
        )


__all__ = ["CustomerAgent"]
