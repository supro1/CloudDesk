from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.nodes._common import tracer_for
from agents.state import SupportState
from backend.app.repositories.workflow import CustomerMemoryRepository
from memory.long_term import LongTermMemory

MEMORY_UPDATE = "memory_update"


def create_memory_update_node(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[SupportState], object]:
    async def memory_update(state: SupportState) -> dict[str, object]:
        plan = state["resolution_plan"]
        steps = [step.instruction for step in state["diagnosis"].steps]
        async with (
            tracer_for().node(MEMORY_UPDATE),
            session_factory() as session,
        ):
            records = await LongTermMemory(
                CustomerMemoryRepository(session)
            ).record_resolution(
                customer_id=state["customer_id"],
                source_ticket_id=state["ticket_id"],
                ticket_body=state["body"],
                summary=state["classification"].summary,
                troubleshooting_steps=steps,
                resolution=plan.summary,
            )
            await session.commit()
        return {
            "memory_updated_count": len(records),
            "completed_nodes": [MEMORY_UPDATE],
            "current_node": MEMORY_UPDATE,
        }

    return memory_update


__all__ = ["MEMORY_UPDATE", "create_memory_update_node"]
