from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agents.nodes._common import tracer_for
from agents.specialists.customer import CustomerAgent
from agents.specialists.knowledge import KnowledgeAgent
from agents.specialists.troubleshooting import TroubleshootingAgent
from agents.state import SupportState
from backend.app.repositories.workflow import CustomerMemoryRepository
from backend.app.tools.registry import ToolRegistry
from memory.long_term import LongTermMemory

CUSTOMER_CONTEXT = "customer_context"
KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
TROUBLESHOOTING = "troubleshooting"


def create_customer_context_node(
    tools: ToolRegistry,
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[SupportState], Awaitable[dict[str, object]]]:
    async def customer_context(state: SupportState) -> dict[str, object]:
        async with (
            tracer_for().node(CUSTOMER_CONTEXT) as observation,
            session_factory() as session,
        ):
            context = await CustomerAgent(
                tools,
                LongTermMemory(CustomerMemoryRepository(session)),
            ).run(state["customer_id"])
        return {
            "customer_context": context,
            "completed_nodes": [CUSTOMER_CONTEXT],
            "current_node": CUSTOMER_CONTEXT,
            "token_usage": observation.token_usage,
        }

    return customer_context


def create_knowledge_retrieval_node(
    tools: ToolRegistry,
) -> Callable[[SupportState], Awaitable[dict[str, object]]]:
    async def knowledge_retrieval(state: SupportState) -> dict[str, object]:
        async with tracer_for().node(KNOWLEDGE_RETRIEVAL) as observation:
            result = await KnowledgeAgent(tools).run(
                f"{state['subject']}\n{state['body']}",
                category=state["category"],
            )
        return {
            "knowledge": result,
            "completed_nodes": [KNOWLEDGE_RETRIEVAL],
            "current_node": KNOWLEDGE_RETRIEVAL,
            "token_usage": observation.token_usage,
        }

    return knowledge_retrieval


def create_troubleshooting_node(
    tools: ToolRegistry,
) -> Callable[[SupportState], Awaitable[dict[str, object]]]:
    async def troubleshooting(state: SupportState) -> dict[str, object]:
        async with tracer_for().node(TROUBLESHOOTING) as observation:
            diagnosis = await TroubleshootingAgent(tools).run(
                f"{state['subject']}\n{state['body']}",
                state["category"],
                state["knowledge"].evidence,
            )
        return {
            "diagnosis": diagnosis,
            "completed_nodes": [TROUBLESHOOTING],
            "current_node": TROUBLESHOOTING,
            "token_usage": observation.token_usage,
        }

    return troubleshooting


__all__ = [
    "CUSTOMER_CONTEXT",
    "KNOWLEDGE_RETRIEVAL",
    "TROUBLESHOOTING",
    "create_customer_context_node",
    "create_knowledge_retrieval_node",
    "create_troubleshooting_node",
]
